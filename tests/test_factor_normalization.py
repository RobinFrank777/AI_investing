import contextlib
import io
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_normalization as normalization


def snapshot(rows=None):
    rows = rows or [
        ["A", "2026-08-05", "PASS", 1.0, 3.0, .3],
        ["B", "2026-08-05", "PASS", 2.0, 2.0, .2],
        ["C", "2026-08-05", "PASS", 3.0, 1.0, .1],
    ]
    return pd.DataFrame(rows, columns=[
        "Ticker", "AsOfDate", "FactorStatus", "TrendValue",
        "MomentumValue", "Volatility20D",
    ])


class FactorNormalizationTests(unittest.TestCase):
    def test_higher_is_better(self):
        result = normalization.normalize_factor_series(pd.Series([1, 2, 3]))
        self.assertEqual(result.tolist(), [1/3, 2/3, 1])

    def test_lower_is_better(self):
        result = normalization.normalize_factor_series(pd.Series([1, 2, 3]), higher_is_better=False)
        self.assertEqual(result.tolist(), [1, 2/3, 1/3])

    def test_range_zero_to_one(self):
        result = normalization.normalize_factor_series(pd.Series(range(10)))
        self.assertTrue(result.between(0, 1).all())

    def test_ties_average(self):
        self.assertEqual(normalization.normalize_factor_series(pd.Series([1, 1, 2])).tolist(), [.5, .5, 1])

    def test_missing_stays_missing(self):
        self.assertTrue(pd.isna(normalization.normalize_factor_series(pd.Series([1, None, 2])).iloc[1]))

    def test_infinite_is_missing(self):
        result = normalization.normalize_factor_series(pd.Series([1, math.inf, 2]))
        self.assertTrue(pd.isna(result.iloc[1]))

    def test_series_not_mutated(self):
        source = pd.Series(["1", "2"]); before = source.copy(); normalization.normalize_factor_series(source)
        pd.testing.assert_series_equal(source, before)

    def test_series_deterministic(self):
        source = pd.Series([3, 1, 2]); pd.testing.assert_series_equal(normalization.normalize_factor_series(source), normalization.normalize_factor_series(source))

    def test_empty_series(self):
        self.assertTrue(normalization.normalize_factor_series(pd.Series(dtype=float)).empty)

    def test_one_valid_is_missing(self):
        self.assertTrue(normalization.normalize_factor_series(pd.Series([1, None])).isna().all())

    def test_two_valid_normalize(self):
        self.assertEqual(normalization.normalize_factor_series(pd.Series([1, 2])).tolist(), [.5, 1])

    def test_constant_values(self):
        self.assertEqual(normalization.normalize_factor_series(pd.Series([2, 2])).tolist(), [.75, .75])

    def test_invalid_method(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            normalization.normalize_factor_series(pd.Series([1, 2]), method="zscore")

    def test_fixed_columns(self):
        self.assertEqual(list(normalization.build_normalized_factor_table(snapshot())), normalization.NORMALIZED_COLUMNS)

    def test_one_row_per_input(self):
        self.assertEqual(len(normalization.build_normalized_factor_table(snapshot())), 3)

    def test_input_order_preserved(self):
        self.assertEqual(normalization.build_normalized_factor_table(snapshot()).Ticker.tolist(), ["A", "B", "C"])

    def test_trend_direction(self):
        self.assertEqual(normalization.build_normalized_factor_table(snapshot()).TrendPercentile.tolist(), [1/3, 2/3, 1])

    def test_momentum_direction(self):
        self.assertEqual(normalization.build_normalized_factor_table(snapshot()).MomentumPercentile.tolist(), [1, 2/3, 1/3])

    def test_low_volatility_direction(self):
        self.assertEqual(normalization.build_normalized_factor_table(snapshot()).LowVolatilityPercentile.tolist(), [1/3, 2/3, 1])

    def test_missing_one_is_partial(self):
        data = snapshot(); data.loc[0, "MomentumValue"] = None
        self.assertEqual(normalization.build_normalized_factor_table(data).loc[0, "NormalizationStatus"], "PARTIAL")

    def test_missing_all_is_failed(self):
        data = snapshot(); data.loc[0, ["TrendValue", "MomentumValue", "Volatility20D"]] = None
        self.assertEqual(normalization.build_normalized_factor_table(data).loc[0, "NormalizationStatus"], "FAILED")

    def test_complete_is_pass(self):
        self.assertTrue((normalization.build_normalized_factor_table(snapshot()).NormalizationStatus == "PASS").all())

    def test_missing_factor_string_order(self):
        data = snapshot(); data.loc[0, ["TrendValue", "Volatility20D"]] = None
        self.assertEqual(normalization.build_normalized_factor_table(data).loc[0, "NormalizationMissingFactors"], "TrendValue;Volatility20D")

    def test_snapshot_not_mutated(self):
        data = snapshot(); before = data.copy(deep=True); normalization.build_normalized_factor_table(data)
        pd.testing.assert_frame_equal(data, before)

    def test_metadata_preserved(self):
        result = normalization.build_normalized_factor_table(snapshot())
        self.assertEqual(result[["Ticker", "AsOfDate", "FactorStatus"]].iloc[0].tolist(), ["A", "2026-08-05", "PASS"])

    def test_mixed_dates_allowed_and_marked(self):
        data = snapshot(); data.loc[1, "AsOfDate"] = "2026-08-04"
        self.assertTrue((normalization.build_normalized_factor_table(data).NormalizationMessage == "Mixed AsOfDate values").all())

    def test_duplicate_tickers_retained(self):
        data = snapshot(); data.loc[1, "Ticker"] = "A"
        self.assertEqual(normalization.build_normalized_factor_table(data).Ticker.tolist(), ["A", "A", "C"])

    def test_table_deterministic(self):
        a = normalization.build_normalized_factor_table(snapshot()); b = normalization.build_normalized_factor_table(snapshot()); pd.testing.assert_frame_equal(a, b)

    def test_diagnostic_counts(self):
        data = snapshot(); data.loc[0, "TrendValue"] = None; result = normalization.build_factor_diagnostics(data)["factors"]["TrendValue"]
        self.assertEqual((result["valid_count"], result["missing_count"]), (2, 1))

    def test_diagnostic_min_max(self):
        result = normalization.build_factor_diagnostics(snapshot())["factors"]["TrendValue"]
        self.assertEqual((result["min"], result["max"]), (1.0, 3.0))

    def test_diagnostic_mean_std(self):
        result = normalization.build_factor_diagnostics(snapshot())["factors"]["TrendValue"]
        self.assertEqual(result["mean"], 2.0); self.assertEqual(result["std"], 1.0)

    def test_diagnostic_unique(self):
        self.assertEqual(normalization.build_factor_diagnostics(snapshot())["factors"]["TrendValue"]["unique_count"], 3)

    def test_mixed_date_warning(self):
        data = snapshot(); data.loc[0, "AsOfDate"] = "2026-08-04"
        self.assertIn("Mixed AsOfDate values", normalization.build_factor_diagnostics(data)["warnings"])

    def test_small_sample_warning(self):
        data = snapshot(); data.loc[1:, "TrendValue"] = None
        self.assertTrue(any(x.startswith("Small normalization sample: TrendValue") for x in normalization.build_factor_diagnostics(data)["warnings"]))

    def test_constant_warning(self):
        data = snapshot(); data["TrendValue"] = 1
        self.assertIn("Constant factor values: TrendValue", normalization.build_factor_diagnostics(data)["warnings"])

    def test_diagnostics_python_types(self):
        result = normalization.build_factor_diagnostics(snapshot())
        self.assertIsInstance(result["row_count"], int); self.assertIsInstance(result["factors"]["TrendValue"]["mean"], float)

    @patch("factor_normalization.build_normalized_factor_table", return_value=pd.DataFrame([{"Ticker": "A"}]))
    def test_output_directory_created(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "out.csv"; normalization.save_normalized_factor_table(snapshot(), path); self.assertTrue(path.parent.is_dir())

    @patch("factor_normalization.build_normalized_factor_table", return_value=pd.DataFrame([{"Ticker": "A"}]))
    def test_csv_created_no_index(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = normalization.save_normalized_factor_table(snapshot(), Path(directory) / "out.csv")
            self.assertEqual(list(pd.read_csv(path)), ["Ticker"])

    @patch("factor_normalization.build_normalized_factor_table", return_value=pd.DataFrame([{"Ticker": "A"}]))
    def test_explicit_output_honored(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wanted.csv"; self.assertEqual(normalization.save_normalized_factor_table(snapshot(), path), path)

    @patch("factor_normalization.save_normalized_factor_table")
    @patch("factor_normalization.build_factor_snapshot_table", return_value=snapshot())
    def test_default_cli_builds_snapshot_without_network(self, builder, save):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.csv"; normalization.build_normalized_factor_table(snapshot()).to_csv(path, index=False); save.return_value = path
            self.assertEqual(normalization.main([]), 0); builder.assert_called_once_with()

    def test_cli_missing_input_nonzero(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(normalization.main(["--input", "/missing/snapshot.csv"]), 1)

    def test_cli_error_has_no_traceback(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output): normalization.main(["--input", "/missing/snapshot.csv"])
        self.assertNotIn("Traceback", output.getvalue())

    def test_missing_required_column_raises(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            normalization.build_normalized_factor_table(snapshot().drop(columns="TrendValue"))


if __name__ == "__main__":
    unittest.main()
