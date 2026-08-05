import tempfile
import unittest
from pathlib import Path

import pandas as pd

from universe_manager import load_universe, validate_universe


class UniverseManagerTests(unittest.TestCase):
    def write_csv(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "watchlist.csv"
        pd.DataFrame(data).to_csv(path, index=False)
        return path

    def test_normal_read_preserves_order(self):
        path = self.write_csv({"Ticker": ["AAPL", "AMD", "NVDA"]})
        self.assertEqual(load_universe(path), ["AAPL", "AMD", "NVDA"])

    def test_normalizes_case_and_whitespace(self):
        path = self.write_csv({"Ticker": [" aapl ", "NvDa"]})
        self.assertEqual(load_universe(path), ["AAPL", "NVDA"])

    def test_deduplicates_in_first_seen_order(self):
        path = self.write_csv(
            {"Ticker": ["AAPL", "AMD", "aapl", "NVDA", "AMD"]}
        )
        summary = validate_universe(path)
        self.assertEqual(summary["symbols"], ["AAPL", "AMD", "NVDA"])
        self.assertEqual(summary["duplicate_rows"], 2)
        self.assertEqual(summary["duplicates"], ["AAPL", "AMD"])

    def test_filters_empty_values(self):
        path = self.write_csv({"Ticker": [None, float("nan"), "", "   ", "AAPL"]})
        self.assertEqual(load_universe(path), ["AAPL"])

    def test_missing_enabled_column_enables_all_valid_rows(self):
        path = self.write_csv({"Ticker": ["AAPL", "AMD"]})
        summary = validate_universe(path)
        self.assertEqual(summary["enabled_rows"], 2)
        self.assertEqual(summary["disabled_rows"], 0)

    def test_enabled_column_filters_values(self):
        values = [True, False, 1, 0, "yes", "no", "enabled", "disabled", "active", "inactive"]
        tickers = [f"T{i}" for i in range(len(values))]
        path = self.write_csv({"Ticker": tickers, "Enabled": values})
        self.assertEqual(load_universe(path), ["T0", "T2", "T4", "T6", "T8"])

    def test_unrecognized_enabled_value_warns_and_disables(self):
        path = self.write_csv({"Ticker": ["AAPL"], "Enabled": ["maybe"]})
        summary = validate_universe(path)
        self.assertEqual(summary["symbols"], [])
        self.assertTrue(any("unrecognized" in item for item in summary["warnings"]))

    def test_allows_supported_special_tickers(self):
        path = self.write_csv({"Ticker": ["BRK.B", "BRK-B", "BF.B", "RDS-A"]})
        self.assertEqual(load_universe(path), ["BRK.B", "BRK-B", "BF.B", "RDS-A"])

    def test_excludes_and_reports_invalid_tickers(self):
        invalid = ["AAPL/USD", "AAPL TEST", "<script>", "中国股票", "AAPL;rm"]
        path = self.write_csv({"Ticker": invalid + ["AAPL"]})
        summary = validate_universe(path)
        self.assertEqual(summary["symbols"], ["AAPL"])
        self.assertEqual(summary["invalid_rows"], len(invalid))
        self.assertEqual(
            [entry["normalized"] for entry in summary["invalid_entries"]],
            [value.upper() for value in invalid],
        )

    def test_missing_file_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                load_universe(Path(directory) / "missing.csv")

    def test_missing_ticker_column_raises_value_error(self):
        path = self.write_csv({"Symbol": ["AAPL"]})
        with self.assertRaisesRegex(ValueError, "Ticker"):
            validate_universe(path)

    def test_empty_universe_returns_warning(self):
        path = self.write_csv({"Ticker": []})
        summary = validate_universe(path)
        self.assertEqual(summary["symbols"], [])
        self.assertTrue(summary["warnings"])

    def test_load_and_validate_symbols_are_consistent(self):
        path = self.write_csv({"Ticker": [" amd ", "AMD", "NVDA"]})
        self.assertEqual(load_universe(path), validate_universe(path)["symbols"])

    def test_repeated_calls_are_deterministic(self):
        path = self.write_csv({"Ticker": ["AAPL", "AMD", "aapl"]})
        self.assertEqual(validate_universe(path), validate_universe(path))


if __name__ == "__main__":
    unittest.main()
