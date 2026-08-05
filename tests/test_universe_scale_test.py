import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import universe_scale_test


class UniverseScaleTestTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.universe_path = self.root / "scale.csv"
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()

    def write_universe(self, tickers, column="Ticker"):
        pd.DataFrame({column: tickers}).to_csv(self.universe_path, index=False)

    def write_data(self, symbol, data):
        path = self.data_dir / f"{symbol}.csv"
        pd.DataFrame(data).to_csv(path, index=False)
        return path

    @patch("universe_scale_test.load_universe", return_value=["AAPL", "AMD"])
    def test_load_scale_universe_uses_manager_and_preserves_order(self, mocked):
        self.assertEqual(
            universe_scale_test.load_scale_test_universe(self.universe_path),
            ["AAPL", "AMD"],
        )
        mocked.assert_called_once_with(self.universe_path)

    @patch("universe_scale_test.load_scale_test_universe")
    def test_limit_selects_first_symbols_in_order(self, mocked):
        mocked.return_value = ["AAPL", "AMD", "NVDA"]
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, limit=2
        )
        self.assertEqual(report["symbols"], ["AAPL", "AMD"])

    def test_invalid_function_limits_raise(self):
        for limit in (0, -1, "2", 1.5, True):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    universe_scale_test.run_scale_validation(
                        self.universe_path, self.data_dir, limit=limit
                    )

    def test_missing_local_file_is_counted(self):
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["missing_files"], 1)
        self.assertEqual(summary["symbols_missing_data"], ["AAPL"])

    def test_normal_csv_is_valid(self):
        self.write_data(
            "AAPL", {"Date": ["2026-08-05"], "Close": [200.0]}
        )
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["valid_files"], 1)
        self.assertEqual(summary["symbols_with_data"], ["AAPL"])

    def test_empty_file_is_invalid(self):
        (self.data_dir / "AAPL.csv").touch()
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["invalid_files"], 1)

    def test_missing_date_column_is_invalid(self):
        self.write_data("AAPL", {"Close": [200.0]})
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["invalid_files"], 1)
        self.assertIn("Date", summary["invalid_entries"][0]["reasons"][0])

    def test_missing_close_column_is_invalid(self):
        self.write_data("AAPL", {"Date": ["2026-08-05"]})
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["invalid_files"], 1)
        self.assertIn("Close", summary["invalid_entries"][0]["reasons"][0])

    def test_invalid_dates_do_not_crash_inspection(self):
        self.write_data("AAPL", {"Date": ["not-a-date"], "Close": [200.0]})
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["invalid_files"], 1)
        self.assertTrue(summary["warnings"])

    def test_total_bytes_counts_existing_valid_and_invalid_files(self):
        first = self.write_data(
            "AAPL", {"Date": ["2026-08-05"], "Close": [200.0]}
        )
        second = self.data_dir / "AMD.csv"
        second.touch()
        summary = universe_scale_test.inspect_local_data(
            ["AAPL", "AMD", "NVDA"], self.data_dir
        )
        self.assertEqual(summary["total_bytes"], first.stat().st_size + second.stat().st_size)

    def test_latest_date_uses_maximum_valid_date(self):
        self.write_data(
            "AAPL",
            {"Date": ["2026-08-01", "bad", "2026-08-05"], "Close": [1, 2, 3]},
        )
        summary = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(summary["latest_dates"], {"AAPL": "2026-08-05"})

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_offline_validation_does_not_download(self, mock_download):
        self.write_universe(["AAPL"])
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=False
        )
        mock_download.assert_not_called()
        self.assertEqual(report["download_summary"]["attempted"], 0)

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_download_processes_symbols_in_order(self, mock_download):
        self.write_universe(["AAPL", "AMD", "NVDA"])
        universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        self.assertEqual(
            mock_download.call_args_list,
            [call("AAPL"), call("AMD"), call("NVDA")],
        )

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_download_failure_continues_and_updates_statistics(self, mock_download):
        self.write_universe(["AAPL", "AMD", "NVDA"])
        mock_download.side_effect = [None, RuntimeError("failed"), None]
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        self.assertEqual(mock_download.call_count, 3)
        self.assertEqual(report["download_summary"]["attempted"], 3)
        self.assertEqual(report["download_summary"]["succeeded"], 2)
        self.assertEqual(report["download_summary"]["failed"], 1)
        self.assertEqual(report["download_summary"]["failed_symbols"], ["AMD"])

    @patch("universe_scale_test.inspect_local_data")
    @patch("universe_scale_test.update_data.update_one_stock")
    def test_download_is_followed_by_local_inspection(self, mock_download, mock_inspect):
        self.write_universe(["AAPL"])
        mock_inspect.return_value = {
            "existing_files": 1,
            "missing_files": 0,
            "valid_files": 1,
            "invalid_files": 0,
            "total_bytes": 10,
            "latest_dates": {"AAPL": "2026-08-05"},
            "symbols_with_data": ["AAPL"],
            "symbols_missing_data": [],
            "invalid_entries": [],
            "warnings": [],
        }
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        mock_download.assert_called_once_with("AAPL")
        mock_inspect.assert_called_once_with(["AAPL"], self.data_dir)
        self.assertEqual(report["valid_files"], 1)

    def test_inspection_is_deterministic(self):
        self.write_data(
            "AAPL", {"Date": ["2026-08-05"], "Close": [200.0]}
        )
        first = universe_scale_test.inspect_local_data(["AAPL", "AMD"], self.data_dir)
        second = universe_scale_test.inspect_local_data(["AAPL", "AMD"], self.data_dir)
        self.assertEqual(first, second)

    def test_empty_universe_returns_zero_statistics_and_warning(self):
        self.write_universe([])
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir
        )
        self.assertEqual(report["symbol_count"], 0)
        self.assertEqual(report["existing_files"], 0)
        self.assertTrue(report["warnings"])

    def test_missing_universe_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            universe_scale_test.run_scale_validation(
                self.root / "missing.csv", self.data_dir
            )

    def test_universe_without_ticker_column_preserves_value_error(self):
        self.write_universe(["AAPL"], column="Symbol")
        with self.assertRaisesRegex(ValueError, "Ticker"):
            universe_scale_test.run_scale_validation(
                self.universe_path, self.data_dir
            )

    @patch("universe_scale_test.run_scale_validation")
    def test_cli_defaults_to_offline(self, mock_run):
        mock_run.return_value = self.report_fixture(download=False)
        self.assertEqual(universe_scale_test.main([]), 0)
        self.assertFalse(mock_run.call_args.kwargs["download"])

    @patch("universe_scale_test.run_scale_validation")
    def test_cli_download_flag_is_explicit(self, mock_run):
        mock_run.return_value = self.report_fixture(download=True)
        self.assertEqual(universe_scale_test.main(["--download"]), 0)
        self.assertTrue(mock_run.call_args.kwargs["download"])

    @patch(
        "universe_scale_test.run_scale_validation",
        side_effect=FileNotFoundError("missing"),
    )
    def test_cli_runtime_error_returns_nonzero(self, _):
        self.assertEqual(universe_scale_test.main([]), 1)

    def test_cli_invalid_limit_exits_nonzero(self):
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value):
                with self.assertRaises(SystemExit) as raised:
                    universe_scale_test.main(["--limit", value])
                self.assertNotEqual(raised.exception.code, 0)

    @staticmethod
    def report_fixture(download):
        return {
            "universe_path": Path("scale.csv"),
            "download_enabled": download,
            "symbol_count": 0,
            "existing_files": 0,
            "missing_files": 0,
            "valid_files": 0,
            "invalid_files": 0,
            "total_bytes": 0,
            "elapsed_seconds": 0.0,
            "download_summary": {
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "failed_symbols": [],
                "elapsed_seconds": 0.0,
                "average_seconds_per_symbol": 0.0,
            },
            "warnings": [],
        }


if __name__ == "__main__":
    unittest.main()
