import contextlib
import io
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_composite as composite


def normalized(rows=None):
    rows = rows or [
        ["A", "2026-08-05", "PASS", .2, .4, .9],
        ["B", "2026-08-05", "PASS", .8, .6, .3],
        ["C", "2026-08-05", "PASS", .5, .5, .5],
    ]
    return pd.DataFrame(rows, columns=[
        "Ticker", "AsOfDate", "NormalizationStatus", "TrendPercentile",
        "MomentumPercentile", "LowVolatilityPercentile",
    ])


class FactorCompositeTests(unittest.TestCase):
    def test_default_weights_validate(self):
        self.assertEqual(composite.validate_factor_weights()["group_weights"], composite.DEFAULT_GROUP_WEIGHTS)

    def test_default_effective_weights(self):
        self.assertEqual(composite.validate_factor_weights()["effective_weights"], {"TrendPercentile": .35, "MomentumPercentile": .35, "LowVolatilityPercentile": .3})

    def test_negative_weight_raises(self):
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            composite.validate_factor_weights({"TrendPercentile": -1, "MomentumPercentile": 2})

    def test_infinite_weight_raises(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            composite.validate_factor_weights({"TrendPercentile": math.inf, "MomentumPercentile": 0})

    def test_non_numeric_weight_raises(self):
        with self.assertRaisesRegex(ValueError, "numeric"):
            composite.validate_factor_weights({"TrendPercentile": "x", "MomentumPercentile": 0})

    def test_missing_key_raises(self):
        with self.assertRaisesRegex(ValueError, "missing keys"):
            composite.validate_factor_weights({"TrendPercentile": 1})

    def test_extra_key_raises(self):
        with self.assertRaisesRegex(ValueError, "unsupported keys"):
            composite.validate_factor_weights({"TrendPercentile": .5, "MomentumPercentile": .5, "Other": 0})

    def test_incorrect_sum_raises(self):
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            composite.validate_factor_weights({"TrendPercentile": .4, "MomentumPercentile": .4})

    def test_zero_total_raises(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            composite.validate_factor_weights({"TrendPercentile": 0, "MomentumPercentile": 0})

    def test_weight_dicts_not_mutated(self):
        strength = {"TrendPercentile": .4, "MomentumPercentile": .6}; before = strength.copy(); composite.validate_factor_weights(strength); self.assertEqual(strength, before)

    def row(self, **overrides):
        value = {"TrendPercentile": .8, "MomentumPercentile": .6, "LowVolatilityPercentile": .5}; value.update(overrides); return value

    def test_strength_score(self):
        self.assertEqual(composite.calculate_composite_row(self.row())["StrengthScore"], .7)

    def test_risk_quality_score(self):
        self.assertEqual(composite.calculate_composite_row(self.row())["RiskQualityScore"], .5)

    def test_composite_score(self):
        self.assertAlmostEqual(composite.calculate_composite_row(self.row())["CompositeFactorScore"], .64)

    def test_contributions_sum(self):
        result = composite.calculate_composite_row(self.row())
        self.assertAlmostEqual(sum(result[x] for x in ["TrendContribution", "MomentumContribution", "LowVolatilityContribution"]), result["CompositeFactorScore"])

    def test_score_in_range(self):
        self.assertTrue(0 < composite.calculate_composite_row(self.row())["CompositeFactorScore"] <= 1)

    def test_source_row_not_mutated(self):
        row = self.row(); before = row.copy(); composite.calculate_composite_row(row); self.assertEqual(row, before)

    def test_strict_missing_no_score(self):
        self.assertIsNone(composite.calculate_composite_row(self.row(MomentumPercentile=None))["CompositeFactorScore"])

    def test_missing_factors_deterministic(self):
        result = composite.calculate_composite_row(self.row(TrendPercentile=None, LowVolatilityPercentile=None))
        self.assertEqual(result["CompositeMissingFactors"], "TrendPercentile;LowVolatilityPercentile")

    def test_none_available_failed(self):
        result = composite.calculate_composite_row(self.row(TrendPercentile=None, MomentumPercentile=None, LowVolatilityPercentile=None))
        self.assertEqual(result["CompositeStatus"], "FAILED")

    def test_partial_availability_partial(self):
        self.assertEqual(composite.calculate_composite_row(self.row(MomentumPercentile=None))["CompositeStatus"], "PARTIAL")

    def test_complete_pass(self):
        self.assertEqual(composite.calculate_composite_row(self.row())["CompositeStatus"], "PASS")

    def test_infinite_input_missing(self):
        self.assertEqual(composite.calculate_composite_row(self.row(TrendPercentile=math.inf))["CompositeStatus"], "PARTIAL")

    def test_row_deterministic(self):
        self.assertEqual(composite.calculate_composite_row(self.row()), composite.calculate_composite_row(self.row()))

    def test_renormalize_not_silent(self):
        with self.assertRaisesRegex(ValueError, "unsupported missing policy"):
            composite.calculate_composite_row(self.row(), missing_policy="renormalize")

    def test_fixed_columns(self):
        self.assertEqual(list(composite.build_composite_factor_table(normalized())), composite.COMPOSITE_COLUMNS)

    def test_one_row_per_input(self):
        self.assertEqual(len(composite.build_composite_factor_table(normalized())), 3)

    def test_universe_order_preserved(self):
        self.assertEqual(composite.build_composite_factor_table(normalized()).Ticker.tolist(), ["A", "B", "C"])

    def test_source_dataframe_not_mutated(self):
        data = normalized(); before = data.copy(deep=True); composite.build_composite_factor_table(data); pd.testing.assert_frame_equal(data, before)

    def test_duplicate_tickers_retained(self):
        data = normalized(); data.loc[1, "Ticker"] = "A"; self.assertEqual(composite.build_composite_factor_table(data).Ticker.tolist(), ["A", "A", "C"])

    def test_mixed_dates_messaged(self):
        data = normalized(); data.loc[1, "AsOfDate"] = "2026-08-04"
        self.assertTrue(composite.build_composite_factor_table(data).CompositeMessage.str.contains("Mixed").all())

    def test_custom_valid_weights(self):
        groups = {"StrengthScore": .8, "RiskQualityScore": .2}
        result = composite.build_composite_factor_table(normalized(), group_weights=groups)
        self.assertAlmostEqual(result.loc[0, "CompositeFactorScore"], .42)

    def test_invalid_custom_weights_fail(self):
        with self.assertRaises(ValueError): composite.build_composite_factor_table(normalized(), group_weights={"StrengthScore": .2, "RiskQualityScore": .2})

    def test_no_hidden_imputation(self):
        data = normalized(); data.loc[0, "TrendPercentile"] = None
        self.assertTrue(pd.isna(composite.build_composite_factor_table(data).loc[0, "CompositeFactorScore"]))

    def test_higher_score_ranks_first(self):
        ranked = composite.build_composite_ranking(composite.build_composite_factor_table(normalized()))
        self.assertEqual(ranked.iloc[0].CompositeRank, 1)

    def test_missing_scores_last(self):
        data = normalized(); data.loc[0, "TrendPercentile"] = None
        ranked = composite.build_composite_ranking(composite.build_composite_factor_table(data)); self.assertEqual(ranked.iloc[-1].Ticker, "A")

    def test_ties_average_rank(self):
        data = normalized([["A", "2026-08-05", "PASS", .5, .5, .5], ["B", "2026-08-05", "PASS", .5, .5, .5]])
        self.assertEqual(composite.build_composite_factor_table(data).CompositeRank.tolist(), [1.5, 1.5])

    def test_ties_display_stable(self):
        data = normalized([["B", "2026-08-05", "PASS", .5, .5, .5], ["A", "2026-08-05", "PASS", .5, .5, .5]])
        self.assertEqual(composite.build_composite_ranking(composite.build_composite_factor_table(data)).Ticker.tolist(), ["B", "A"])

    def test_ranking_source_not_mutated(self):
        data = composite.build_composite_factor_table(normalized()); before = data.copy(deep=True); composite.build_composite_ranking(data); pd.testing.assert_frame_equal(data, before)

    def test_composite_percentile_direction(self):
        table = composite.build_composite_factor_table(normalized()); best = table.CompositeFactorScore.idxmax(); self.assertEqual(table.loc[best, "CompositePercentile"], 1)

    def test_ranking_deterministic(self):
        data = composite.build_composite_factor_table(normalized()); pd.testing.assert_frame_equal(composite.build_composite_ranking(data), composite.build_composite_ranking(data))

    def test_diagnostic_statistics(self):
        data = composite.build_composite_factor_table(normalized()); result = composite.build_composite_diagnostics(data)
        self.assertEqual(result["complete_score_count"], 3); self.assertAlmostEqual(result["score_mean"], data.CompositeFactorScore.mean())

    def test_diagnostic_effective_weights(self):
        self.assertEqual(composite.build_composite_diagnostics(composite.build_composite_factor_table(normalized()))["effective_weights"]["TrendPercentile"], .35)

    def test_high_correlation_warning(self):
        data = normalized(); data["MomentumPercentile"] = data["TrendPercentile"]
        result = composite.build_composite_diagnostics(composite.build_composite_factor_table(data)); self.assertIn("High Trend/Momentum correlation", result["warnings"])

    def test_warning_does_not_modify_scores_or_weights(self):
        data = composite.build_composite_factor_table(normalized()); before = data.copy(deep=True); composite.build_composite_diagnostics(data); pd.testing.assert_frame_equal(data, before)

    def test_missing_ratio_warning(self):
        data = normalized(); data.loc[:1, "TrendPercentile"] = None
        result = composite.build_composite_diagnostics(composite.build_composite_factor_table(data)); self.assertTrue(any(x.startswith("High missing score ratio") for x in result["warnings"]))

    def test_constant_score_warning(self):
        data = normalized([["A", "2026-08-05", "PASS", .5, .5, .5], ["B", "2026-08-05", "PASS", .5, .5, .5]])
        self.assertIn("Constant CompositeFactorScore", composite.build_composite_diagnostics(composite.build_composite_factor_table(data))["warnings"])

    def test_diagnostics_python_values(self):
        result = composite.build_composite_diagnostics(composite.build_composite_factor_table(normalized())); self.assertIsInstance(result["row_count"], int); self.assertIsInstance(result["score_mean"], float)

    def test_sensitivity_schemes(self):
        result = composite.build_weight_sensitivity(normalized(), top_n=2); self.assertEqual(list(result), list(composite.SENSITIVITY_SCHEMES)); self.assertEqual(result["Baseline"]["top_overlap_count"], 2)

    @patch("factor_composite.build_composite_factor_table", return_value=pd.DataFrame([{"Ticker": "A"}]))
    def test_output_directory_created(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "out.csv"; composite.save_composite_factor_table(normalized(), path); self.assertTrue(path.parent.is_dir())

    @patch("factor_composite.build_composite_factor_table", return_value=pd.DataFrame([{"Ticker": "A"}]))
    def test_csv_created_without_index(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = composite.save_composite_factor_table(normalized(), Path(directory) / "out.csv"); self.assertEqual(list(pd.read_csv(path)), ["Ticker"])

    @patch("factor_composite.build_composite_factor_table", return_value=pd.DataFrame([{"Ticker": "A"}]))
    def test_explicit_output_honored(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wanted.csv"; self.assertEqual(composite.save_composite_factor_table(normalized(), path), path)

    @patch("factor_composite.save_composite_factor_table")
    @patch("factor_composite.build_normalized_factor_table", return_value=normalized())
    def test_default_cli_no_network(self, builder, save):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.csv"; composite.build_composite_factor_table(normalized()).to_csv(path, index=False); save.return_value = path
            self.assertEqual(composite.main([]), 0); builder.assert_called_once_with()

    def test_invalid_input_nonzero(self):
        with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(composite.main(["--input", "/missing/file.csv"]), 1)

    def test_expected_error_no_traceback(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output): composite.main(["--input", "/missing/file.csv"])
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
