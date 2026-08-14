import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import order_draft
import order_review
import portfolio_risk
import position_sizing
from config import PRIMARY_UNIVERSE_VERSION
from portfolio_risk_calculator import RISK_MODEL_VERSION


CAPITAL = 100_000
TOLERANCE = 0.01


def qualified_candidates(count=3):
    tickers = ["AAPL", "MSFT", "NVDA"] + [f"TEST{i:02d}" for i in range(max(0, count - 3))]
    return pd.DataFrame({
        "Ticker": tickers[:count],
        "RunId": ["run-1"] * count, "AsOfDate": ["2026-06-18"] * count,
        "UniverseVersion": [PRIMARY_UNIVERSE_VERSION] * count,
        "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * count,
        "RiskModelVersion": [RISK_MODEL_VERSION] * count,
        "CandidateRank": range(1, count + 1),
        "FinalScore": list(range(100, 100 - count, -1)),
        "TradeSignal": ["BUY"] * count, "Eligibility": ["ELIGIBLE"] * count,
        "PortfolioEligible": [True] * count, "RiskStatus": ["RISK_READY"] * count,
        "RiskReadyForPortfolio": [True] * count,
        "LatestClose": [100.0] * count, "LatestCloseAsOf": ["2026-06-18"] * count,
        "MaxDrawdown": [-0.05] * count,
        "SharpeRatio": [2.5] * count,
        "RiskLevel": ["Low"] * count, "RiskWeightMultiplier": [1.0] * count,
        "FundamentalScore": [75.0] * count,
        "CombinedScore": list(range(100, 100 - count, -1)),
        "FundamentalRating": ["GOOD"] * count,
    })


def enrich_empty_portfolio(portfolio):
    result = portfolio.copy()
    for column, dtype in (
        ("FundamentalScore", "float64"),
        ("CombinedScore", "float64"),
        ("FundamentalRating", "object"),
    ):
        if column not in result:
            result[column] = pd.Series(dtype=dtype)
    return result


def run_flow(candidates, prices=None, capital=CAPITAL):
    portfolio = portfolio_risk.build_model_portfolio(candidates)
    portfolio = enrich_empty_portfolio(portfolio)
    sized = position_sizing.add_target_dollar_amount(portfolio, capital)
    prices = prices or {ticker: 100.0 for ticker in sized.get("Ticker", [])}
    with patch.object(
        position_sizing,
        "get_latest_close",
        side_effect=lambda ticker: prices[ticker],
    ):
        sized = position_sizing.add_share_sizing(sized)
    draft = order_draft.build_order_draft(sized)
    review = order_review.build_order_review(draft)
    return portfolio, sized, draft, review


class CapitalFlowContractTests(unittest.TestCase):
    def assert_capital_invariants(self, portfolio, sized, draft):
        self.assertLessEqual(len(portfolio), portfolio_risk.MAX_HOLDINGS)
        if not portfolio.empty:
            weights = portfolio.TargetWeight.to_numpy(dtype=float)
            self.assertTrue(np.isfinite(weights).all())
            self.assertTrue((weights >= 0).all())
            self.assertTrue((weights <= portfolio_risk.MAX_POSITION_WEIGHT + 1e-12).all())
            self.assertLessEqual(weights.sum(), portfolio_risk.MAX_TOTAL_EXPOSURE + 1e-12)
        if not sized.empty:
            self.assertTrue((sized.TargetDollarAmount.dropna() >= 0).all())
            self.assertTrue((sized.TargetShares >= 0).all())
            self.assertTrue(all(float(value).is_integer() for value in sized.TargetShares))
        if not draft.empty:
            self.assertTrue((draft.TargetShares > 0).all())
            self.assertTrue(np.isfinite(draft[["TargetShares", "LatestClose", "EstimatedOrderValue"]]).all().all())
            allocated = float(sized.TargetDollarAmount.fillna(0).sum())
            drafted = float(draft.EstimatedOrderValue.sum())
            self.assertLessEqual(drafted, allocated + TOLERANCE)
            self.assertGreaterEqual(CAPITAL - drafted, -TOLERANCE)

    def test_normal_single_and_multiple_candidate_flows(self):
        for count in (1, 3):
            with self.subTest(count=count):
                flow = run_flow(qualified_candidates(count))
                self.assertEqual(len(flow[0]), count)
                self.assertEqual(len(flow[2]), count)
                self.assertTrue((flow[3].ReviewStatus == "PASS").all())
                self.assertTrue((flow[3].PortfolioReviewFlag == "PASS").all())
                self.assert_capital_invariants(*flow[:3])

    def test_more_and_fewer_than_max_holdings(self):
        many = run_flow(qualified_candidates(portfolio_risk.MAX_HOLDINGS + 3))
        few = run_flow(qualified_candidates(2))
        self.assertEqual(len(many[0]), portfolio_risk.MAX_HOLDINGS)
        self.assertEqual(len(few[0]), 2)
        self.assert_capital_invariants(*many[:3])
        self.assert_capital_invariants(*few[:3])

    def test_no_action_end_to_end(self):
        portfolio, sized, draft, reviewed = run_flow(qualified_candidates(0))
        self.assertTrue(portfolio.empty)
        self.assertEqual(portfolio.attrs["PortfolioStatus"], portfolio_risk.NO_QUALIFIED_CANDIDATES)
        self.assertTrue(sized.empty)
        self.assertTrue(draft.empty)
        self.assertEqual(draft.attrs["OrderDraftStatus"], order_draft.NO_DRAFT_ORDERS)
        self.assertEqual(reviewed.attrs["ReviewStatus"], order_review.NO_ORDERS_TO_REVIEW)
        self.assertEqual(reviewed.attrs["PortfolioReviewFlag"], "NOT_APPLICABLE")

    def test_all_unknown_invalid_and_zero_multiplier_no_action(self):
        unknown = qualified_candidates(3); unknown["SharpeRatio"] = np.nan
        invalid = qualified_candidates(3); invalid["FinalScore"] = [np.nan, np.inf, -np.inf]
        for label, data in (("unknown", unknown), ("invalid", invalid)):
            with self.subTest(label=label):
                flow = run_flow(data)
                self.assertTrue(flow[0].empty); self.assertTrue(flow[2].empty)
                self.assertEqual(flow[3].attrs["PortfolioReviewFlag"], "NOT_APPLICABLE")
        zero = qualified_candidates(2); zero["RiskWeightMultiplier"] = 0.0
        flow = run_flow(zero)
        self.assertEqual(flow[0].attrs["PortfolioStatus"], portfolio_risk.NO_RISK_READY_CANDIDATES)

    def test_unknown_high_rank_does_not_occupy_slots(self):
        data = qualified_candidates(portfolio_risk.MAX_HOLDINGS + 2)
        data.loc[:1, "SharpeRatio"] = np.nan
        portfolio, sized, draft, reviewed = run_flow(data)
        self.assertEqual(len(portfolio), portfolio_risk.MAX_HOLDINGS)
        self.assertNotIn("AAPL", portfolio.Ticker.tolist())
        self.assertEqual(len(draft), portfolio_risk.MAX_HOLDINGS)
        self.assert_capital_invariants(portfolio, sized, draft)

    def test_invalid_prices_produce_no_orders(self):
        for price in (0.0, -1.0, np.nan, np.inf, -np.inf):
            with self.subTest(price=price):
                portfolio, sized, draft, reviewed = run_flow(
                    qualified_candidates(1), {"AAPL": price}
                )
                self.assertEqual(sized.at[0, "SizingStatus"], position_sizing.INVALID_PRICE)
                self.assertTrue(draft.empty)
                self.assertEqual(reviewed.attrs["PortfolioReviewFlag"], "NOT_APPLICABLE")

    def test_zero_share_and_zero_capital_remain_no_action(self):
        high_price = run_flow(qualified_candidates(1), {"AAPL": 1_000_000.0})
        zero_capital = run_flow(qualified_candidates(1), capital=0)
        for flow in (high_price, zero_capital):
            self.assertEqual(flow[1].at[0, "TargetShares"], 0)
            self.assertTrue(flow[2].empty)
            self.assertEqual(flow[3].attrs["PortfolioReviewFlag"], "NOT_APPLICABLE")

    def test_invalid_capital_and_weight_are_safe(self):
        portfolio = portfolio_risk.build_model_portfolio(qualified_candidates(1))
        for capital in (np.nan, np.inf, -1):
            with self.subTest(capital=capital), self.assertRaises(ValueError):
                position_sizing.add_target_dollar_amount(portfolio, capital)
        for weight in (np.nan, -1.0):
            data = portfolio.copy(); data.loc[:, "TargetWeight"] = weight
            sized = position_sizing.add_target_dollar_amount(data, CAPITAL)
            self.assertEqual(sized.at[0, "SizingStatus"], position_sizing.INVALID_SIZING_INPUT)

    def test_injected_invalid_orders_cannot_pass(self):
        _, sized, _, _ = run_flow(qualified_candidates(1))
        for field, value in (
            ("TargetShares", -1), ("TargetShares", 0), ("TargetShares", 1.5),
            ("TargetShares", np.nan), ("TargetShares", np.inf),
            ("LatestClose", 0), ("TargetDollarAmount", np.nan),
        ):
            injected = sized.copy(); injected[field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(order_draft.build_order_draft(injected).empty)

    def test_missing_fundamentals_propagates_review_required(self):
        data = qualified_candidates(1); data["FundamentalRating"] = "MISSING"
        portfolio, sized, draft, reviewed = run_flow(data)
        self.assertEqual(reviewed.at[0, "ReviewStatus"], "REVIEW")
        self.assertEqual(reviewed.at[0, "PortfolioReviewFlag"], "REVIEW_REQUIRED")
        self.assert_capital_invariants(portfolio, sized, draft)

    def test_review_and_blocked_aggregate_severity(self):
        _, _, draft, _ = run_flow(qualified_candidates(2))
        review_row = draft.iloc[[0]].copy(); review_row["FundamentalRating"] = "MISSING"
        blocked_row = draft.iloc[[1]].copy(); blocked_row["TargetShares"] = 0
        passing = draft.iloc[[0]].copy()
        self.assertEqual(
            order_review.build_order_review(pd.concat([passing, review_row])).PortfolioReviewFlag.iloc[0],
            "REVIEW_REQUIRED",
        )
        for frames in ([passing, blocked_row], [review_row, blocked_row]):
            reviewed = order_review.build_order_review(pd.concat(frames))
            self.assertEqual(reviewed.PortfolioReviewFlag.iloc[0], "BLOCKED")

    def test_cash_reconciliation_and_residual_cash(self):
        portfolio, sized, draft, _ = run_flow(
            qualified_candidates(3), {"AAPL": 333.0, "MSFT": 457.0, "NVDA": 129.0}
        )
        target_from_weights = float(portfolio.TargetWeight.sum() * CAPITAL)
        allocated = float(sized.TargetDollarAmount.sum())
        drafted = float(draft.EstimatedOrderValue.sum())
        self.assertAlmostEqual(allocated, target_from_weights, places=2)
        self.assertLessEqual(drafted, allocated + TOLERANCE)
        self.assertGreater(allocated - drafted, 0)
        self.assertGreaterEqual(CAPITAL - drafted, -TOLERANCE)
        self.assertLess(portfolio.TargetWeight.sum(), portfolio_risk.MAX_TOTAL_EXPOSURE)


if __name__ == "__main__":
    unittest.main()
