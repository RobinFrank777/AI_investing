import math
import unittest

import pandas as pd

from price_factors import (
    calculate_momentum_value,
    calculate_price_factors,
    calculate_trend_value,
    calculate_volatility_20d,
)


def frame(values, dates=False):
    data = {"Close": values}
    if dates:
        data["Date"] = pd.date_range("2024-01-01", periods=len(values))
    return pd.DataFrame(data)


class PriceFactorTests(unittest.TestCase):
    def test_non_dataframe_raises(self):
        with self.assertRaisesRegex(ValueError, "DataFrame"):
            calculate_trend_value([1, 2])

    def test_missing_close_raises(self):
        with self.assertRaisesRegex(ValueError, "Close"):
            calculate_momentum_value(pd.DataFrame({"Open": [1]}))

    def test_source_not_mutated(self):
        data = frame([str(x) for x in range(60)], dates=True); before = data.copy()
        calculate_price_factors(data); pd.testing.assert_frame_equal(data, before)

    def test_numeric_strings_accepted(self):
        self.assertEqual(calculate_momentum_value(frame(["1"] * 20 + ["2"])), 1.0)

    def test_invalid_close_removed(self):
        values = list(range(1, 22)); values.insert(10, "bad")
        self.assertAlmostEqual(calculate_momentum_value(frame(values)), 20.0)

    def test_infinity_removed_and_never_returned(self):
        value = calculate_momentum_value(frame([1] * 20 + [math.inf, 2]))
        self.assertEqual(value, 1.0); self.assertTrue(math.isfinite(value))

    def test_trend_equal_ma_is_zero(self):
        self.assertEqual(calculate_trend_value(frame([5] * 60)), 0.0)

    def test_trend_above_is_positive(self):
        self.assertGreater(calculate_trend_value(frame([1] * 59 + [2])), 0)

    def test_trend_below_is_negative(self):
        self.assertLess(calculate_trend_value(frame([2] * 59 + [1])), 0)

    def test_trend_insufficient(self):
        self.assertIsNone(calculate_trend_value(frame([1] * 59)))

    def test_trend_exact_boundary(self):
        self.assertIsNotNone(calculate_trend_value(frame(range(1, 61))))

    def test_trend_manual_value(self):
        self.assertAlmostEqual(calculate_trend_value(frame(range(1, 61))), 60 / 30.5 - 1)

    def test_momentum_positive(self):
        self.assertAlmostEqual(calculate_momentum_value(frame(range(1, 22))), 20.0)

    def test_momentum_negative(self):
        self.assertAlmostEqual(calculate_momentum_value(frame(range(21, 0, -1))), 1 / 21 - 1)

    def test_momentum_flat(self):
        self.assertEqual(calculate_momentum_value(frame([7] * 21)), 0.0)

    def test_momentum_insufficient(self):
        self.assertIsNone(calculate_momentum_value(frame([1] * 20)))

    def test_momentum_exact_boundary(self):
        self.assertIsNotNone(calculate_momentum_value(frame([1] * 21)))

    def test_momentum_zero_base_missing(self):
        self.assertIsNone(calculate_momentum_value(frame([0] + [1] * 20)))

    def test_momentum_uses_t_minus_20(self):
        values = [1, 100] + [2] * 19
        self.assertEqual(calculate_momentum_value(frame(values)), 1.0)

    def test_volatility_constant_zero(self):
        self.assertEqual(calculate_volatility_20d(frame([5] * 21)), 0.0)

    def test_volatility_matches_pandas(self):
        values = pd.Series(range(1, 22), dtype=float)
        self.assertAlmostEqual(calculate_volatility_20d(frame(values)), values.pct_change().iloc[1:].std(ddof=1))

    def test_volatility_insufficient(self):
        self.assertIsNone(calculate_volatility_20d(frame([1] * 20)))

    def test_volatility_exact_boundary(self):
        self.assertIsNotNone(calculate_volatility_20d(frame(range(1, 22))))

    def test_volatility_uses_sample_ddof(self):
        values = pd.Series(range(1, 22), dtype=float); result = calculate_volatility_20d(frame(values))
        self.assertAlmostEqual(result, values.pct_change().iloc[1:].std(ddof=1)); self.assertNotAlmostEqual(result, values.pct_change().iloc[1:].std(ddof=0))

    def test_volatility_daily_decimal(self):
        values = pd.Series(range(10, 31), dtype=float)
        self.assertAlmostEqual(calculate_volatility_20d(frame(values)), values.pct_change().iloc[1:].std())

    def test_volatility_not_annualized(self):
        values = pd.Series(range(10, 31), dtype=float); result = calculate_volatility_20d(frame(values))
        self.assertNotAlmostEqual(result, values.pct_change().iloc[1:].std() * 252 ** .5)

    def test_volatility_not_percent(self):
        values = pd.Series(range(10, 31), dtype=float); result = calculate_volatility_20d(frame(values))
        self.assertNotAlmostEqual(result, values.pct_change().iloc[1:].std() * 100)

    def test_wrapper_fixed_keys(self):
        self.assertEqual(list(calculate_price_factors(frame([1] * 60))), ["TrendValue", "MomentumValue", "Volatility20D"])

    def test_wrapper_agrees_with_individuals(self):
        data = frame(range(1, 61)); result = calculate_price_factors(data)
        self.assertEqual(result["TrendValue"], calculate_trend_value(data)); self.assertEqual(result["MomentumValue"], calculate_momentum_value(data)); self.assertEqual(result["Volatility20D"], calculate_volatility_20d(data))

    def test_repeated_input_deterministic(self):
        data = frame(range(1, 61)); self.assertEqual(calculate_price_factors(data), calculate_price_factors(data))

    def test_valid_dates_are_sorted(self):
        data = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=21)[::-1], "Close": range(1, 22)})
        self.assertAlmostEqual(calculate_momentum_value(data), 1 / 21 - 1)

    def test_duplicate_dates_are_stably_retained(self):
        dates = list(pd.date_range("2024-01-01", periods=20)) + [pd.Timestamp("2024-01-20")]
        self.assertEqual(calculate_momentum_value(pd.DataFrame({"Date": dates, "Close": range(1, 22)})), 20.0)


if __name__ == "__main__":
    unittest.main()
