import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import portfolio_risk as subject


def candidates(count=3):
    return pd.DataFrame({
        "Ticker": [f"T{i:02d}" for i in range(count)],
        "BacktestScore": list(range(100, 100-count, -1)),
        "AverageReturn": [0.1] * count,
        "WinRate": [0.6] * count,
        "MaxDrawdown": [-0.05] * count,
        "SharpeRatio": [2.5] * count,
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
        data["BacktestScore"] = [np.nan, np.inf, -np.inf]
        result = subject.build_model_portfolio(data)
        self.assertTrue(result.empty)
        self.assertEqual(result.attrs["PortfolioStatus"], subject.NO_RISK_READY_CANDIDATES)

    def test_nan_inf_negative_and_zero_multiplier_are_not_sized(self):
        for value in (np.nan, np.inf, -np.inf, -1.0, 0.0):
            with self.subTest(value=value), patch.dict(
                subject.RISK_LEVEL_WEIGHT_MULTIPLIERS, {"Low": value}
            ):
                result = subject.build_model_portfolio(candidates(2))
                self.assertTrue(result.empty)
                self.assertEqual(result.attrs["PortfolioStatus"], subject.NO_SIZABLE_POSITIONS)

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
        data["BacktestScore"] = 100
        result = subject.build_model_portfolio(data)
        self.assertEqual(result.Ticker.tolist(), ["T00", "T01", "T02"])

    def test_input_is_not_modified_and_downstream_columns_remain(self):
        data = candidates(2); before = data.copy(deep=True)
        result = subject.build_model_portfolio(data)
        pd.testing.assert_frame_equal(data, before)
        for column in ("Ticker", "BacktestScore", "RiskLevel", "RiskWeightMultiplier", "TargetWeight", "TargetWeightPercent", "PortfolioRole"):
            self.assertIn(column, result.columns)


if __name__ == "__main__":
    unittest.main()
