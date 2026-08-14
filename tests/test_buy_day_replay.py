import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import buy_day_replay as subject
from current_run_status import CURRENT_RUN_STATUS_PATH
from config import (
    MODEL_PORTFOLIO_OUTPUT_PATH, ORDER_DRAFT_OUTPUT_PATH,
    ORDER_REVIEW_OUTPUT_PATH, POSITION_SIZING_OUTPUT_PATH,
)
from portfolio_candidate_adapter import DEFAULT_INPUT_PATH as PRODUCTION_CANDIDATE_PATH
from portfolio_risk_calculator import DEFAULT_OUTPUT_PATH as RISK_INPUT_PATH
from order_review import build_order_review
from portfolio_risk import MAX_HOLDINGS, MAX_POSITION_WEIGHT, MAX_TOTAL_EXPOSURE


TICKERS = ["SNDK", "ARM", "MU", "WDC", "MRVL", "STX", "INTC", "NBIS"]


def score_snapshot():
    tickers = TICKERS + ["WATCH1"]
    count = len(tickers)
    return pd.DataFrame({
        "Ticker": tickers,
        "Date": pd.to_datetime(["2026-06-18"] * count),
        "FinalScore": [80 - index * 0.5 for index in range(8)] + [65.0],
        "RS_Score": [90 - index for index in range(count)],
        "NearHighScore": [20] * count,
        "Confidence": [85.0] * count,
        "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * count,
        "Volume_Ratio": [1.2] * 8 + [0.5],
        "DistanceToHigh": [0.97] * 8 + [0.90],
        "Close": [120.0] * count,
        "MA20": [110.0] * count,
        "MA60": [100.0] * count,
    })


def market(end="2026-06-18", future=False):
    dates = pd.bdate_range(end=pd.Timestamp(end), periods=90)
    increments = np.resize(np.array([0.4, 0.7, -0.2, 0.5, 0.1]), len(dates))
    close = 100 + np.cumsum(increments)
    frame = pd.DataFrame({
        "Date": dates, "High": close * 1.01, "Low": close * .99,
        "Close": close, "Volume": np.linspace(1_000_000, 1_200_000, len(dates)),
    })
    if future:
        extra = pd.DataFrame({
            "Date": pd.bdate_range("2026-06-19", periods=5),
            "High": 999.0, "Low": 1.0, "Close": 500.0, "Volume": 9_000_000,
        })
        frame = pd.concat([frame, extra], ignore_index=True)
    return frame


def markets(future=False):
    return {ticker: market(future=future) for ticker in TICKERS}


def fundamentals():
    return pd.DataFrame({
        "Ticker": TICKERS, "FundamentalScore": [75.0] * 8,
        "CombinedScore": [80 - index * 0.5 for index in range(8)],
        "FundamentalRating": ["GOOD"] * 8,
    })


class BuyDayReplayTests(unittest.TestCase):
    def run_replay(self, future=False, fundamentals_table=None):
        return subject.run_buy_day_replay(
            scores=score_snapshot(), market_data=markets(future=future),
            calculation_timestamp="2026-06-18T22:00:00+00:00",
            fundamentals=fundamentals() if fundamentals_table is None else fundamentals_table,
        )

    def test_full_replay_is_non_empty_safe_and_reconciled(self):
        result = self.run_replay()
        candidates, risk, portfolio = result["candidates"], result["risk_inputs"], result["portfolio"]
        sizing, draft, review = result["sizing"], result["draft"], result["review"]
        self.assertEqual((candidates.TradeSignal == "BUY").sum(), 8)
        self.assertEqual((candidates.Eligibility == "ELIGIBLE").sum(), 8)
        self.assertEqual(candidates.loc[candidates.Eligibility == "ELIGIBLE", "Ticker"].tolist(), TICKERS)
        self.assertEqual(int(risk.RiskReadyForPortfolio.sum()), 8)
        self.assertTrue((risk.LatestCloseAsOf <= risk.AsOfDate).all())
        self.assertGreater(len(portfolio), 0); self.assertLessEqual(len(portfolio), MAX_HOLDINGS)
        self.assertLessEqual(float(portfolio.TargetWeight.sum()), MAX_TOTAL_EXPOSURE + 1e-12)
        self.assertLessEqual(float(portfolio.TargetWeight.max()), MAX_POSITION_WEIGHT + 1e-12)
        self.assertEqual(len(sizing), len(portfolio)); self.assertGreater(len(draft), 0)
        self.assertTrue((sizing.TargetShares >= 0).all())
        self.assertTrue(all(float(value).is_integer() for value in sizing.TargetShares))
        allocated = float(sizing.TargetDollarAmount.sum()); drafted = float(draft.EstimatedOrderValue.sum())
        self.assertLessEqual(drafted, allocated); self.assertGreaterEqual(subject.REPLAY_CAPITAL - drafted, 0)
        self.assertEqual((review.ReviewStatus == "PASS").sum(), len(review))
        self.assertEqual(review.PortfolioReviewFlag.unique().tolist(), ["PASS"])

    def test_future_rows_do_not_change_replay_and_replay_is_deterministic(self):
        first = self.run_replay(); second = self.run_replay(); future = self.run_replay(future=True)
        for key in ("candidates", "risk_inputs", "portfolio", "sizing", "draft", "review"):
            pd.testing.assert_frame_equal(first[key].reset_index(drop=True), second[key].reset_index(drop=True))
            pd.testing.assert_frame_equal(first[key].reset_index(drop=True), future[key].reset_index(drop=True))

    def test_metadata_propagates_through_review(self):
        result = self.run_replay()
        fields = ("RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion", "RiskModelVersion")
        for name in ("risk_inputs", "portfolio", "sizing", "draft", "review"):
            frame = result[name]
            for field in fields:
                self.assertIn(field, frame.columns)
                self.assertEqual(frame[field].nunique(), 1)

    def test_review_boundaries_remain_mechanical(self):
        result = self.run_replay()
        missing = result["draft"].copy(); missing["FundamentalRating"] = "MISSING"
        reviewed = build_order_review(missing)
        self.assertTrue((reviewed.ReviewStatus == "REVIEW").all())
        self.assertEqual(reviewed.PortfolioReviewFlag.unique().tolist(), ["REVIEW_REQUIRED"])
        invalid = result["draft"].copy(); invalid.loc[invalid.index[0], "LatestClose"] = np.inf
        blocked = build_order_review(invalid)
        self.assertEqual(blocked.loc[blocked.index[0], "ReviewStatus"], "BLOCKED")
        self.assertEqual(blocked.PortfolioReviewFlag.unique().tolist(), ["BLOCKED"])

    def test_replay_does_not_change_current_run_identity_or_production_artifacts(self):
        paths = (
            Path(CURRENT_RUN_STATUS_PATH), Path(PRODUCTION_CANDIDATE_PATH),
            Path(RISK_INPUT_PATH), Path(MODEL_PORTFOLIO_OUTPUT_PATH),
            Path(POSITION_SIZING_OUTPUT_PATH), Path(ORDER_DRAFT_OUTPUT_PATH),
            Path(ORDER_REVIEW_OUTPUT_PATH),
        )
        before = {path: path.read_bytes() if path.is_file() else None for path in paths}
        self.run_replay()
        after = {path: path.read_bytes() if path.is_file() else None for path in paths}
        self.assertEqual(before, after)

    def test_no_legacy_forward_selection_or_broker_transmission(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("backtest_qualified_20d", source)
        self.assertNotIn("Forward5DReturn", source)
        self.assertNotIn("Forward20DReturn", source)
        self.assertNotIn("Forward60DReturn", source)
        self.assertNotIn("broker", source.lower())


if __name__ == "__main__":
    unittest.main()
