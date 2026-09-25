import contextlib
import io
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import combined_scoring
import fundamental_scoring
import order_draft
import order_review
import position_sizing


BUY_TICKER = "BUY1"
OTHER_TICKER = "OTHER"
BACKTEST_SCORE = 71.237


def _production_metadata_snapshot():
    """Read names and mtimes only; never open production artifact contents."""
    snapshot = {}
    repo_root = Path(__file__).resolve().parents[1]
    for directory_name in ("data", "results"):
        directory = repo_root / directory_name
        if not directory.exists():
            snapshot[directory_name] = None
            continue
        files = {}
        for root, _, names in os.walk(directory):
            root_path = Path(root)
            for name in names:
                file_path = root_path / name
                stat = file_path.stat()
                files[str(file_path.relative_to(directory))] = stat.st_mtime_ns
        snapshot[directory_name] = files
    return snapshot


def _fundamental_row(ticker, quality):
    if quality == "strong":
        values = [0.40, 0.40, 0.80, 0.40, 0.40, 0.30, 0.0, 10.0, 2.0]
    elif quality == "weak":
        values = [-0.10, -0.10, 0.10, -0.10, -0.10, -0.10, 3.0, 100.0, 50.0]
    else:
        raise ValueError(quality)
    return dict(zip(fundamental_scoring.REQUIRED_COLUMNS, [ticker, *values]))


def _model_portfolio_row():
    return {
        "Ticker": BUY_TICKER,
        "BacktestScore": BACKTEST_SCORE,
        "AverageReturn": 0.10,
        "WinRate": 0.60,
        "MaxDrawdown": -0.10,
        "SharpeRatio": 2.0,
        "RiskLevel": "Low",
        "RiskReady": True,
        "RiskWeightMultiplier": 1.0,
        "TargetWeight": 0.05,
        "TargetWeightPercent": "5.0%",
        "PortfolioRole": "candidate",
        "PortfolioStatus": "PORTFOLIO_READY",
        "LatestClose": 100.0,
        "LatestCloseAsOf": "2026-09-25",
        "RunId": "test-run",
        "AsOfDate": "2026-09-25",
        "ScoreModelVersion": "test-score-model",
        "RiskModelVersion": "test-risk-model",
    }


class MissingDataPropagationRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.production_metadata_before = _production_metadata_snapshot()

    @classmethod
    def tearDownClass(cls):
        cls.production_metadata_after = _production_metadata_snapshot()
        if cls.production_metadata_before != cls.production_metadata_after:
            raise AssertionError(
                "Tests changed production data/results paths or modification times"
            )

    def test_a_missing_fundamental_contributes_zero_and_rounds(self):
        model = pd.DataFrame([{"Ticker": BUY_TICKER, "BacktestScore": BACKTEST_SCORE}])
        fundamentals = pd.DataFrame(
            [{"Ticker": OTHER_TICKER, "FundamentalScore": 90.0, "FundamentalRating": "STRONG"}]
        )

        result = combined_scoring.calculate_combined_score(model, fundamentals)
        unrounded = BACKTEST_SCORE * combined_scoring.BACKTEST_SCORE_WEIGHT

        self.assertNotEqual(unrounded, round(unrounded, 2))
        self.assertEqual(result.at[0, "FundamentalScore"], 0)
        self.assertEqual(
            result.at[0, "CombinedScore"],
            round(BACKTEST_SCORE * combined_scoring.BACKTEST_SCORE_WEIGHT, 2),
        )

    def test_b_position_sizing_fallbacks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            combined_path = root / "combined_score.csv"
            pd.DataFrame(
                [
                    {"Ticker": "NO_FUND", "FundamentalScore": pd.NA, "CombinedScore": 50.0, "FundamentalRating": "GOOD"},
                    {"Ticker": "NO_COMBINED", "FundamentalScore": 10.0, "CombinedScore": pd.NA, "FundamentalRating": "WEAK"},
                    {"Ticker": "NO_RATING", "FundamentalScore": 10.0, "CombinedScore": 50.0, "FundamentalRating": pd.NA},
                ]
            ).to_csv(combined_path, index=False)
            portfolio = pd.DataFrame(
                [
                    {"Ticker": ticker, "BacktestScore": BACKTEST_SCORE, "TargetWeight": 0.05, "LatestClose": 100.0}
                    for ticker in ("NO_FUND", "NO_COMBINED", "NO_RATING")
                ]
            )

            with patch.object(position_sizing, "COMBINED_SCORE_INPUT", combined_path), patch.object(
                position_sizing, "STOCK_DATA_DIR", root / "prices"
            ), patch.object(
                position_sizing,
                "get_latest_close",
                side_effect=AssertionError("real stock prices must not be read"),
            ):
                enriched = position_sizing.add_combined_scores(portfolio)
                sized = position_sizing.add_share_sizing(
                    position_sizing.add_target_dollar_amount(enriched)
                ).set_index("Ticker")

            self.assertEqual(sized.at["NO_FUND", "FundamentalScore"], 0)
            self.assertEqual(sized.at["NO_COMBINED", "CombinedScore"], BACKTEST_SCORE)
            self.assertEqual(sized.at["NO_RATING", "FundamentalRating"], "MISSING")
            self.assertTrue((sized["SizingStatus"] == position_sizing.POSITION_READY).all())

    def _run_chain(self, fundamental_quality):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {
                "fundamentals": root / "fundamentals.csv",
                "fundamental_score": root / "fundamental_score.csv",
                "model_portfolio": root / "model_portfolio.csv",
                "combined_score": root / "combined_score.csv",
                "position_sizing": root / "model_portfolio_sizing.csv",
                "order_draft": root / "order_draft.csv",
                "order_review": root / "order_review.csv",
                "prices": root / "prices",
            }
            paths["prices"].mkdir()

            source_rows = [_fundamental_row(OTHER_TICKER, "strong")]
            if fundamental_quality is not None:
                source_rows.append(_fundamental_row(BUY_TICKER, fundamental_quality))
            pd.DataFrame(source_rows).to_csv(paths["fundamentals"], index=False)
            pd.DataFrame([_model_portfolio_row()]).to_csv(paths["model_portfolio"], index=False)

            with ExitStack() as stack:
                stack.enter_context(patch.object(fundamental_scoring, "FUNDAMENTAL_INPUT", paths["fundamentals"]))
                stack.enter_context(patch.object(fundamental_scoring, "FUNDAMENTAL_SCORE_OUTPUT", paths["fundamental_score"]))
                stack.enter_context(patch.object(combined_scoring, "MODEL_PORTFOLIO_OUTPUT_PATH", paths["model_portfolio"]))
                stack.enter_context(patch.object(combined_scoring, "FUNDAMENTAL_SCORE_OUTPUT_PATH", paths["fundamental_score"]))
                stack.enter_context(patch.object(combined_scoring, "COMBINED_SCORE_OUTPUT_PATH", paths["combined_score"]))
                stack.enter_context(patch.object(position_sizing, "MODEL_PORTFOLIO_INPUT", paths["model_portfolio"]))
                stack.enter_context(patch.object(position_sizing, "COMBINED_SCORE_INPUT", paths["combined_score"]))
                stack.enter_context(patch.object(position_sizing, "POSITION_SIZING_OUTPUT", paths["position_sizing"]))
                stack.enter_context(patch.object(position_sizing, "STOCK_DATA_DIR", paths["prices"]))
                stack.enter_context(patch.object(order_draft, "POSITION_SIZING_INPUT", paths["position_sizing"]))
                stack.enter_context(patch.object(order_draft, "ORDER_DRAFT_OUTPUT", paths["order_draft"]))
                stack.enter_context(patch.object(order_review, "ORDER_DRAFT_INPUT", paths["order_draft"]))
                stack.enter_context(patch.object(order_review, "ORDER_REVIEW_OUTPUT", paths["order_review"]))
                stack.enter_context(
                    patch.object(
                        position_sizing,
                        "get_latest_close",
                        side_effect=AssertionError("real stock prices must not be read"),
                    )
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    fundamental_scoring.print_fundamental_score()
                    combined_scoring.print_combined_score()
                    position_sizing.print_position_sizing()
                    order_draft.print_order_draft()
                    order_review.print_order_review()

            fundamental_output = pd.read_csv(paths["fundamental_score"])
            combined_output = pd.read_csv(paths["combined_score"])
            sizing_output = pd.read_csv(paths["position_sizing"])
            draft_output = pd.read_csv(paths["order_draft"])
            review_output = pd.read_csv(paths["order_review"])
            return {
                "fundamental": fundamental_output,
                "combined": combined_output,
                "sizing": sizing_output,
                "draft": draft_output,
                "review": review_output,
            }

    def test_c_source_missing_fundamental_reaches_review(self):
        outputs = self._run_chain(None)

        self.assertFalse(outputs["fundamental"].empty)
        self.assertEqual(outputs["fundamental"]["Ticker"].tolist(), [OTHER_TICKER])
        self.assertEqual(outputs["combined"].at[0, "FundamentalRating"], "MISSING")
        self.assertEqual(outputs["sizing"].at[0, "FundamentalRating"], "MISSING")
        self.assertEqual(outputs["sizing"].at[0, "TargetWeight"], 0.05)
        self.assertEqual(outputs["sizing"].at[0, "RiskLevel"], "Low")
        self.assertEqual(outputs["sizing"].at[0, "TargetDollarAmount"], 5000.0)
        self.assertEqual(outputs["draft"].at[0, "FundamentalRating"], "MISSING")
        self.assertEqual(outputs["draft"].at[0, "EstimatedOrderValue"], 5000.0)
        self.assertEqual(outputs["review"].at[0, "ReviewStatus"], "REVIEW")
        self.assertEqual(
            outputs["review"].at[0, "ReviewReason"].lower(),
            "fundamental rating missing; manual review required",
        )
        self.assertEqual(outputs["review"].at[0, "PortfolioReviewFlag"], "REVIEW_REQUIRED")

    def test_d_matched_valid_fundamental_control_passes(self):
        outputs = self._run_chain("strong")

        self.assertEqual(outputs["combined"].at[0, "FundamentalRating"], "STRONG")
        self.assertEqual(outputs["review"].at[0, "ReviewStatus"], "PASS")
        self.assertEqual(outputs["review"].at[0, "PortfolioReviewFlag"], "PASS")

    def test_d2_real_weak_fundamental_control_passes(self):
        outputs = self._run_chain("weak")

        self.assertEqual(outputs["combined"].at[0, "FundamentalRating"], "WEAK")
        self.assertLess(outputs["combined"].at[0, "FundamentalScore"], 45)
        self.assertEqual(outputs["review"].at[0, "ReviewStatus"], "PASS")
        self.assertEqual(outputs["review"].at[0, "PortfolioReviewFlag"], "PASS")


if __name__ == "__main__":
    unittest.main()
