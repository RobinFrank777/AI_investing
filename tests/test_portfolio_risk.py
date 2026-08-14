import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import portfolio_risk as subject
from config import PRIMARY_UNIVERSE_VERSION
from portfolio_risk_calculator import RISK_MODEL_VERSION


def candidates(count=3):
    return pd.DataFrame({
        "Ticker": [f"T{i:02d}" for i in range(count)],
        "RunId": ["run-1"] * count, "AsOfDate": ["2026-06-18"] * count,
        "UniverseVersion": [PRIMARY_UNIVERSE_VERSION] * count,
        "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * count,
        "RiskModelVersion": [RISK_MODEL_VERSION] * count,
        "CandidateRank": range(1, count + 1),
        "FinalScore": list(range(100, 100-count, -1)),
        "TradeSignal": ["BUY"] * count, "Eligibility": ["ELIGIBLE"] * count,
        "PortfolioEligible": [True] * count, "RiskStatus": ["RISK_READY"] * count,
        "RiskReadyForPortfolio": [True] * count,
        "LatestClose": [100.0] * count, "LatestCloseAsOf": ["2026-06-18"] * count,
        "MaxDrawdown": [-0.05] * count,
        "SharpeRatio": [2.5] * count,
        "RiskLevel": ["Low"] * count,
        "RiskWeightMultiplier": [1.0] * count,
    })


class PortfolioRiskHardeningTests(unittest.TestCase):
    def assert_safe(self, result):
        if result.empty:
            return
        weights = result.TargetWeight.to_numpy(dtype=float)
        self.assertTrue(np.isfinite(weights).all())
        self.assertTrue((weights >= 0).all())
        self.assertTrue((weights <= subject.MAX_POSITION_WEIGHT + 1e-12).all())
        self.assertLessEqual(weights.sum(), subject.MAX_TOTAL_EXPOSURE + 1e-12)
        self.assertLessEqual(len(result), subject.MAX_HOLDINGS)

    def test_one_and_multiple_valid_candidates_are_safe(self):
        one = subject.build_model_portfolio(candidates(1))
        many = subject.build_model_portfolio(candidates(3))
        self.assertEqual(len(one), 1)
        self.assertEqual(len(many), 3)
        self.assert_safe(one); self.assert_safe(many)

    def test_filter_before_max_holdings_fills_valid_slots(self):
        data = candidates(subject.MAX_HOLDINGS + 3)
        data.loc[:2, ["MaxDrawdown", "SharpeRatio"]] = np.nan
        result = subject.build_model_portfolio(data)
        self.assertEqual(len(result), subject.MAX_HOLDINGS)
        self.assertNotIn("T00", result.Ticker.tolist())
        self.assertIn(f"T{subject.MAX_HOLDINGS + 2:02d}", result.Ticker.tolist())

    def test_fewer_eligible_candidates_are_not_replaced(self):
        data = candidates(5)
        data.loc[2:, "SharpeRatio"] = np.nan
        result = subject.build_model_portfolio(data)
        self.assertEqual(result.Ticker.tolist(), ["T00", "T01"])

    def test_empty_and_all_unknown_return_explicit_states(self):
        empty = subject.build_model_portfolio(candidates(0))
        self.assertEqual(empty.attrs["PortfolioStatus"], subject.NO_QUALIFIED_CANDIDATES)
        unknown = candidates(3); unknown["SharpeRatio"] = np.nan
        result = subject.build_model_portfolio(unknown)
        self.assertEqual(result.attrs["PortfolioStatus"], subject.NO_RISK_READY_CANDIDATES)

    def test_all_invalid_numeric_does_not_crash(self):
        data = candidates(3)
        data["FinalScore"] = [np.nan, np.inf, -np.inf]
        result = subject.build_model_portfolio(data)
        self.assertTrue(result.empty)
        self.assertEqual(result.attrs["PortfolioStatus"], subject.NO_RISK_READY_CANDIDATES)

    def test_nan_inf_negative_and_zero_multiplier_are_not_sized(self):
        for value in (np.nan, np.inf, -np.inf, -1.0, 0.0):
            with self.subTest(value=value):
                data = candidates(2); data["RiskWeightMultiplier"] = value
                result = subject.build_model_portfolio(data)
                self.assertTrue(result.empty)
                self.assertEqual(result.attrs["PortfolioStatus"], subject.NO_RISK_READY_CANDIDATES)

    def test_caps_leave_cash_without_redistribution(self):
        result = subject.build_model_portfolio(candidates(3))
        self.assertTrue((result.TargetWeight == subject.MAX_POSITION_WEIGHT).all())
        self.assertAlmostEqual(result.TargetWeight.sum(), 0.30)
        self.assertLess(result.TargetWeight.sum(), subject.MAX_TOTAL_EXPOSURE)

    def test_total_exposure_cap_with_max_holdings(self):
        result = subject.build_model_portfolio(candidates(subject.MAX_HOLDINGS))
        self.assert_safe(result)
        self.assertLessEqual(
            result.TargetWeight.sum(),
            subject.MAX_TOTAL_EXPOSURE + subject.ALLOCATION_TOLERANCE,
        )

    def test_equal_scores_use_stable_ticker_tie_break(self):
        data = candidates(3).iloc[[2, 0, 1]].copy()
        data["FinalScore"] = 100
        result = subject.build_model_portfolio(data)
        self.assertEqual(result.Ticker.tolist(), ["T00", "T01", "T02"])

    def test_input_is_not_modified_and_downstream_columns_remain(self):
        data = candidates(2); before = data.copy(deep=True)
        result = subject.build_model_portfolio(data)
        pd.testing.assert_frame_equal(data, before)
        for column in ("Ticker", "FinalScore", "RiskLevel", "RiskWeightMultiplier", "TargetWeight", "TargetWeightPercent", "PortfolioRole"):
            self.assertIn(column, result.columns)

    def test_zero_eligible_and_partial_risk_ready_semantics(self):
        none = candidates(2); none["PortfolioEligible"] = False
        result = subject.build_model_portfolio(none)
        self.assertEqual(result.attrs["PortfolioStatus"], subject.NO_QUALIFIED_CANDIDATES)

        partial = candidates(3)
        partial.loc[0, ["RiskReadyForPortfolio", "RiskStatus"]] = [False, "STALE_HISTORY"]
        result = subject.build_model_portfolio(partial)
        self.assertEqual(result.Ticker.tolist(), ["T01", "T02"])
        self.assertEqual(result.attrs["ExcludedRiskCandidates"], [
            {"Ticker": "T00", "RiskStatus": "STALE_HISTORY"}
        ])

    def test_production_schema_does_not_require_legacy_display_fields(self):
        data = candidates(1)
        self.assertNotIn("BacktestScore", data)
        self.assertNotIn("AverageReturn", data)
        self.assertNotIn("WinRate", data)
        result = subject.build_model_portfolio(data)
        self.assertEqual(result.at[0, "FinalScore"], 100)
        self.assertEqual(result.at[0, "BacktestScore"], 100)

    def test_metadata_is_propagated_and_incompatibility_fails_closed(self):
        result = subject.build_model_portfolio(candidates(2))
        for column in ("RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion", "RiskModelVersion"):
            self.assertEqual(result[column].nunique(), 1)
            self.assertEqual(result.at[0, column], candidates(2).at[0, column])

        for column, value in (("RunId", "run-2"), ("AsOfDate", "2026-06-17"),
                              ("ScoreModelVersion", "other"), ("RiskModelVersion", "other")):
            data = candidates(2); data.loc[1, column] = value
            with self.subTest(column=column):
                failed = subject.build_model_portfolio(data)
                self.assertEqual(failed.attrs["PortfolioStatus"], subject.PRODUCTION_RISK_INPUTS_INCOMPATIBLE)

        for column in ("UniverseVersion", "ScoreModelVersion", "RiskModelVersion"):
            data = candidates(1).drop(columns=[column])
            with self.subTest(missing=column):
                failed = subject.build_model_portfolio(data)
                self.assertEqual(failed.attrs["PortfolioStatus"], subject.PRODUCTION_RISK_INPUTS_INCOMPATIBLE)

        data = candidates(1); data.loc[:, "UniverseVersion"] = "legacy"
        failed = subject.build_model_portfolio(data)
        self.assertEqual(failed.attrs["PortfolioStatus"], subject.PRODUCTION_RISK_INPUTS_INCOMPATIBLE)

    def test_final_score_then_rank_then_ticker_determinism(self):
        data = candidates(3).iloc[[2, 0, 1]].copy()
        data["FinalScore"] = [90, 100, 100]
        data["CandidateRank"] = [3, 2, 1]
        first = subject.build_model_portfolio(data)
        second = subject.build_model_portfolio(data)
        self.assertEqual(first.Ticker.tolist(), ["T01", "T00", "T02"])
        pd.testing.assert_frame_equal(first, second)

    def test_source_contains_no_legacy_fallback_or_order_generation(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("backtest_qualified_20d.csv", source)
        self.assertNotIn("BACKTEST_QUALIFIED_20D_OUTPUT_PATH", source)
        self.assertNotIn("order_draft", source)


if __name__ == "__main__":
    unittest.main()
