import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import factor_research_universe as subject


SYMBOLS = [f"S{i:02d}" for i in range(50)]


def market(rows=60):
    return pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=rows),
        "Close": range(1, rows + 1),
    })


class ResearchUniverseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def universe(self, symbols=SYMBOLS, columns=True):
        path = self.root / "universe.csv"
        pd.DataFrame({"Ticker": symbols} if columns else {"Wrong": symbols}).to_csv(path, index=False)
        return path

    def write_market(self, symbol, rows=60, frame=None):
        path = self.root / f"{symbol}.csv"
        (market(rows) if frame is None else frame).to_csv(path, index=False)
        return path

    # Universe loading
    def test_01_loads_exactly_50(self):
        self.assertEqual(len(subject.load_research_universe(self.universe())), 50)

    def test_02_preserves_order(self):
        ordered = list(reversed(SYMBOLS))
        self.assertEqual(subject.load_research_universe(self.universe(ordered)), ordered)

    def test_03_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            subject.load_research_universe(self.root / "missing.csv")

    def test_04_malformed_file_raises(self):
        with self.assertRaises(ValueError):
            subject.load_research_universe(self.universe(columns=False))

    def test_05_wrong_count_raises(self):
        with self.assertRaisesRegex(ValueError, "exactly 50"):
            subject.load_research_universe(self.universe(SYMBOLS[:-1]))

    def test_06_custom_count(self):
        self.assertEqual(subject.load_research_universe(self.universe(SYMBOLS[:2]), expected_symbol_count=2), SYMBOLS[:2])

    def test_07_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            subject.load_research_universe(self.universe(SYMBOLS[:-1] + [SYMBOLS[0]]))

    def test_08_invalid_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            subject.load_research_universe(self.universe(SYMBOLS[:-1] + ["BAD SYMBOL"]))

    def test_09_calls_explicit_loader(self):
        summary = {"duplicate_rows": 0, "invalid_rows": 0}
        with patch.object(subject, "validate_universe", return_value=summary), patch.object(subject, "load_universe", return_value=SYMBOLS) as loader:
            subject.load_research_universe("chosen.csv")
        loader.assert_called_once_with(Path("chosen.csv"))

    def test_10_never_calls_active_universe(self):
        self.assertNotIn("load_active_universe", subject.__dict__)

    # Inspection
    def test_11_complete_files(self):
        for symbol in SYMBOLS[:2]: self.write_market(symbol)
        result = subject.inspect_research_market_data(SYMBOLS[:2], data_dir=self.root)
        self.assertEqual((result["existing_files"], result["valid_files"]), (2, 2))

    def test_12_missing_files(self):
        result = subject.inspect_research_market_data(["A", "B"], data_dir=self.root)
        self.assertEqual(result["symbols_missing_data"], ["A", "B"])

    def test_13_malformed_isolated(self):
        (self.root / "A.csv").write_text('"broken', encoding="utf-8")
        self.write_market("B")
        result = subject.inspect_research_market_data(["A", "B"], data_dir=self.root)
        self.assertEqual((result["invalid_files"], result["valid_files"]), (1, 1))

    def test_14_missing_date_invalid(self):
        self.write_market("A", frame=pd.DataFrame({"Close": [1]}))
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["invalid_files"], 1)

    def test_15_missing_close_invalid(self):
        self.write_market("A", frame=pd.DataFrame({"Date": ["2025-01-01"]}))
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["invalid_files"], 1)

    def test_16_unusable_values_invalid(self):
        self.write_market("A", frame=pd.DataFrame({"Date": ["bad"], "Close": ["bad"]}))
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["invalid_files"], 1)

    def test_17_59_rows_ineligible(self):
        self.write_market("A", 59)
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["factor_eligible_symbols"], [])

    def test_18_60_rows_eligible(self):
        self.write_market("A", 60)
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["factor_eligible_symbols"], ["A"])

    def test_19_120_rows_forward_eligible(self):
        self.write_market("A", 120)
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["forward_validation_eligible_symbols"], ["A"])

    def test_20_119_rows_not_forward_eligible(self):
        self.write_market("A", 119)
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["forward_validation_eligible_symbols"], [])

    def test_21_counts_only_valid_pairs(self):
        self.write_market("A", frame=pd.DataFrame({"Date": ["2025-01-01", "bad"], "Close": [1, 2]}))
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["row_counts"]["A"], 1)

    def test_22_dates_are_deterministic(self):
        self.write_market("A", frame=pd.DataFrame({"Date": ["2025-02-01", "2025-01-01"], "Close": [1, 2]}))
        result = subject.inspect_research_market_data(["A"], data_dir=self.root)
        self.assertEqual((result["first_dates"]["A"], result["latest_dates"]["A"]), ("2025-01-01", "2025-02-01"))

    def test_23_source_not_modified(self):
        path = self.write_market("A"); before = path.read_bytes()
        subject.inspect_research_market_data(["A"], data_dir=self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_24_total_bytes(self):
        path = self.write_market("A")
        self.assertEqual(subject.inspect_research_market_data(["A"], data_dir=self.root)["total_bytes"], path.stat().st_size)

    def test_25_schema_complete(self):
        keys = set(subject.inspect_research_market_data([], data_dir=self.root))
        self.assertEqual(keys, {"symbol_count", "existing_files", "missing_files", "valid_files", "invalid_files", "symbols_with_data", "symbols_missing_data", "invalid_entries", "row_counts", "first_dates", "latest_dates", "total_bytes", "factor_eligible_symbols", "forward_validation_eligible_symbols", "warnings"})

    # Output paths
    def test_26_default_snapshot_path(self):
        self.assertEqual(subject.build_research_output_paths(results_dir=self.root)["snapshot"], self.root / "scale50_factor_snapshot.csv")

    def test_27_all_16_paths(self):
        self.assertEqual(len(subject.build_research_output_paths(results_dir=self.root)), 16)

    def test_28_custom_name(self):
        self.assertTrue(subject.build_research_output_paths("trial_2", self.root)["summary"].name.startswith("trial_2_"))

    def test_29_traversal_rejected(self):
        with self.assertRaises(ValueError): subject.build_research_output_paths("../bad", self.root)

    def test_30_absolute_name_rejected(self):
        with self.assertRaises(ValueError): subject.build_research_output_paths("/bad", self.root)

    def test_31_uppercase_rejected(self):
        with self.assertRaises(ValueError): subject.build_research_output_paths("Scale50", self.root)

    def test_32_caller_directory_respected(self):
        self.assertTrue(all(p.parent == self.root for p in subject.build_research_output_paths(results_dir=self.root).values()))

    def test_33_helper_writes_nothing(self):
        subject.build_research_output_paths(results_dir=self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_34_no_production_names(self):
        names = {p.name for p in subject.build_research_output_paths(results_dir=self.root).values()}
        self.assertTrue(all(name.startswith("scale50_") for name in names))

    # Orchestration / CLI
    def pipeline_patches(self, inspection=None):
        inspection = inspection or {"symbol_count": 50, "existing_files": 50, "missing_files": 0, "valid_files": 50, "invalid_files": 0, "symbols_with_data": SYMBOLS, "symbols_missing_data": [], "invalid_entries": [], "row_counts": {s: 120 for s in SYMBOLS}, "first_dates": {s: "2025-01-01" for s in SYMBOLS}, "latest_dates": {s: "2025-04-30" for s in SYMBOLS}, "total_bytes": 1, "factor_eligible_symbols": SYMBOLS, "forward_validation_eligible_symbols": SYMBOLS, "warnings": []}
        paths = subject.build_research_output_paths(results_dir=self.root)
        table = pd.DataFrame({"RebalanceDate": ["2025-01-31"], "Ticker": ["S00"], "CompositeFactorScore": [1.0], "ForwardReturn5D": [0.1], "ForwardReturn10D": [0.1], "ForwardReturn20D": [0.1], "ForwardReturn60D": [0.1]})
        empty = pd.DataFrame()
        validation_run = {
            "validation": table.copy(), "rank_ic": empty.copy(),
            "group_returns": empty.copy(), "turnover": empty.copy(),
            "summary": {"rows": 1}, "output_paths": {},
        }
        patches = [
            patch.object(subject, "load_research_universe", return_value=SYMBOLS), patch.object(subject, "inspect_research_market_data", return_value=inspection), patch.object(subject, "build_research_output_paths", return_value=paths),
            patch.object(subject, "build_factor_snapshot_table", return_value=table.copy()), patch.object(subject, "build_normalized_factor_table", return_value=table.copy()), patch.object(subject, "build_composite_factor_table", return_value=table.copy()), patch.object(subject, "_read_market_file", return_value=(market(120), pd.Series(pd.date_range("2025-01-01", periods=120)), 120)),
            patch.object(subject, "run_factor_validation", return_value=validation_run), patch.object(subject, "generate_factor_research_report", return_value={"html_path": str(paths["report"]), "json_path": str(paths["report_json"]), "report": {"factors": 3}}), patch.object(subject, "build_alternative_entry_validation", return_value=table.copy()), patch.object(subject, "build_date_contribution_diagnostics", return_value=empty.copy()), patch.object(subject, "build_robust_return_statistics", return_value=empty.copy()), patch.object(subject, "build_symbol_influence_table", return_value=empty.copy()), patch.object(subject, "build_entry_comparison", return_value=empty.copy()), patch.object(subject, "classify_market_regimes", return_value=empty.copy()), patch.object(subject, "build_regime_diagnostics", return_value=empty.copy()), patch.object(subject, "build_coverage_diagnostics", return_value=empty.copy()),
        ]
        return patches

    def run_mocked(self, inspection=None, **kwargs):
        patches = self.pipeline_patches(inspection)
        mocks = [p.start() for p in patches]
        try: return subject.run_factor_research_universe("u.csv", **kwargs), mocks
        finally:
            for p in reversed(patches): p.stop()

    def test_35_offline_false_rejected(self):
        with self.assertRaisesRegex(ValueError, "offline"): subject.run_factor_research_universe("u.csv", offline=False)

    def test_36_explicit_symbols_to_snapshot(self):
        _, mocks = self.run_mocked()
        mocks[3].assert_called_once_with(SYMBOLS, include_runtime_sources=False)

    def test_37_snapshot_passed_to_normalization(self):
        _, mocks = self.run_mocked()
        self.assertIs(mocks[4].call_args.args[0], mocks[3].return_value)

    def test_38_normalized_passed_to_composite(self):
        _, mocks = self.run_mocked()
        self.assertIs(mocks[5].call_args.args[0], mocks[4].return_value)

    def test_39_validation_gets_symbols(self):
        _, mocks = self.run_mocked()
        self.assertEqual(mocks[7].call_args.args[0], SYMBOLS)
        self.assertEqual(mocks[7].call_args.args[1].keys(), dict.fromkeys(SYMBOLS).keys())
        self.assertEqual(
            set(mocks[7].call_args.kwargs["output_paths"]),
            {"validation", "rank_ic", "group_returns", "turnover"},
        )

    def test_39b_validation_paths_are_scale50_specific(self):
        _, mocks = self.run_mocked()
        output_paths = mocks[7].call_args.kwargs["output_paths"]
        self.assertTrue(all(path.name.startswith("scale50_") for path in output_paths.values()))

    def test_39c_report_uses_scale50_output(self):
        _, mocks = self.run_mocked()
        self.assertTrue(mocks[8].call_args.kwargs["html_path"].name.startswith("scale50_"))
        self.assertTrue(mocks[8].call_args.kwargs["json_path"].name.startswith("scale50_"))

    def test_40_strict_missing_stops_before_factors(self):
        inspection = {"symbols_missing_data": ["S00"], "invalid_entries": [], "factor_eligible_symbols": SYMBOLS[1:], "missing_files": 1, "invalid_files": 0}
        with patch.object(subject, "load_research_universe", return_value=SYMBOLS), patch.object(subject, "inspect_research_market_data", return_value=inspection), patch.object(subject, "build_factor_snapshot_table") as snapshot:
            with self.assertRaisesRegex(ValueError, "missing symbol count=1"): subject.run_factor_research_universe("u.csv")
            snapshot.assert_not_called()

    def test_41_partial_labeled_incomplete(self):
        inspection = {"symbol_count": 50, "existing_files": 49, "missing_files": 1, "valid_files": 49, "invalid_files": 0, "symbols_with_data": SYMBOLS[:-1], "symbols_missing_data": ["S49"], "invalid_entries": [], "row_counts": {s: 120 for s in SYMBOLS[:-1]}, "first_dates": {}, "latest_dates": {}, "total_bytes": 1, "factor_eligible_symbols": SYMBOLS[:-1], "forward_validation_eligible_symbols": SYMBOLS[:-1], "warnings": ["Missing market data files: 1"]}
        summary, _ = self.run_mocked(inspection, require_complete_data=False)
        self.assertFalse(summary["complete_data"])

    def test_42_outputs_scale50_specific(self):
        summary, _ = self.run_mocked()
        self.assertTrue(all(Path(value).name.startswith("scale50_") for value in summary["outputs"].values()))

    def test_43_summary_json_compatible(self):
        summary, _ = self.run_mocked()
        json.dumps(summary, allow_nan=False)

    def test_44_repeated_runs_deterministic(self):
        first, _ = self.run_mocked(); second, _ = self.run_mocked()
        self.assertEqual(first, second)

    def test_45_summary_has_six_safety_lines(self):
        summary, _ = self.run_mocked()
        self.assertEqual(len(summary["safety"]), 6)

    def test_46_inspect_only_no_calculation(self):
        with patch.object(subject, "load_research_universe", return_value=SYMBOLS), patch.object(subject, "inspect_research_market_data", return_value={"existing_files": 0, "missing_files": 50, "valid_files": 0, "invalid_files": 0, "factor_eligible_symbols": [], "forward_validation_eligible_symbols": []}), patch.object(subject, "run_factor_research_universe") as run:
            self.assertEqual(subject.main(["--universe", "u.csv", "--inspect-only"]), 0); run.assert_not_called()

    def test_47_inspect_only_writes_nothing(self):
        before = list(self.root.iterdir())
        with patch.object(subject, "load_research_universe", return_value=SYMBOLS), patch.object(subject, "inspect_research_market_data", return_value={"existing_files": 0, "missing_files": 50, "valid_files": 0, "invalid_files": 0, "factor_eligible_symbols": [], "forward_validation_eligible_symbols": []}): subject.main(["--universe", "u.csv", "--inspect-only"])
        self.assertEqual(list(self.root.iterdir()), before)

    def test_48_default_cli_is_offline(self):
        with patch.object(subject, "load_research_universe", return_value=SYMBOLS), patch.object(subject, "run_factor_research_universe", return_value={"complete_data": True, "symbols_used": SYMBOLS}) as run:
            subject.main(["--universe", "u.csv"])
        self.assertTrue(run.call_args.kwargs["offline"])

    def test_49_missing_universe_nonzero(self):
        with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(subject.main(["--universe", str(self.root / "missing")]), 1)

    def test_50_expected_error_no_traceback(self):
        error = io.StringIO()
        with patch.object(subject, "load_research_universe", side_effect=ValueError("expected")), contextlib.redirect_stderr(error): self.assertEqual(subject.main(["--universe", "bad"]), 1)
        self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
