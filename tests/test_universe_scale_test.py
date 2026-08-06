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

    @staticmethod
    def download_result(symbol, status="success", message=""):
        return {
            "symbol": symbol,
            "status": status,
            "rows": 10 if status == "success" else 0,
            "latest_date": "2026-08-05" if status == "success" else None,
            "output_path": f"data/{symbol}.csv" if status != "empty" else None,
            "message": message,
        }

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
        mock_download.side_effect = [
            self.download_result("AAPL"),
            self.download_result("AMD"),
            self.download_result("NVDA"),
        ]
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
        mock_download.side_effect = [
            self.download_result("AAPL"),
            self.download_result("AMD", "failed", "failed"),
            self.download_result("NVDA"),
        ]
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        self.assertEqual(mock_download.call_count, 3)
        self.assertEqual(report["download_summary"]["attempted"], 3)
        self.assertEqual(report["download_summary"]["succeeded"], 2)
        self.assertEqual(report["download_summary"]["empty"], 0)
        self.assertEqual(report["download_summary"]["failed"], 1)
        self.assertEqual(report["download_summary"]["failed_symbols"], ["AMD"])

    @patch("universe_scale_test.inspect_local_data")
    @patch("universe_scale_test.update_data.update_one_stock")
    def test_download_is_followed_by_local_inspection(self, mock_download, mock_inspect):
        self.write_universe(["AAPL"])
        mock_download.return_value = self.download_result("AAPL")
        missing = {
            "existing_files": 0, "missing_files": 1, "valid_files": 0,
            "invalid_files": 0, "symbols_with_data": [],
            "symbols_missing_data": ["AAPL"], "invalid_entries": [],
            "warnings": [],
        }
        valid = {
            "existing_files": 1,
            "missing_files": 0,
            "valid_files": 1,
            "invalid_files": 0,
            "total_bytes": 10,
            "latest_dates": {"AAPL": "2026-08-05"},
            "first_dates": {"AAPL": "2026-08-05"},
            "row_counts": {"AAPL": 1},
            "file_sizes": {"AAPL": 10},
            "symbols_with_data": ["AAPL"],
            "symbols_missing_data": [],
            "invalid_entries": [],
            "warnings": [],
        }
        mock_inspect.side_effect = [missing, valid]
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        mock_download.assert_called_once_with("AAPL")
        self.assertEqual(mock_inspect.call_count, 2)
        mock_inspect.assert_called_with(["AAPL"], self.data_dir)
        self.assertEqual(report["valid_files"], 1)

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_contract_statuses_messages_fields_order_and_invariant(self, mock_download):
        self.write_universe(["AAPL", "AMD", "AVGO"])
        mock_download.side_effect = [
            self.download_result("AAPL"),
            self.download_result("AMD", "empty", "Yahoo returned no data"),
            self.download_result("AVGO", "failed", "connection timeout"),
        ]

        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        summary = report["download_summary"]

        self.assertEqual(summary["attempted"], 3)
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["empty"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["successful_symbols"], ["AAPL"])
        self.assertEqual(summary["empty_symbols"], ["AMD"])
        self.assertEqual(summary["failed_symbols"], ["AVGO"])
        self.assertEqual(
            [result["symbol"] for result in summary["results"]],
            ["AAPL", "AMD", "AVGO"],
        )
        self.assertEqual(len(summary["results"]), summary["attempted"])
        self.assertEqual(
            summary["succeeded"] + summary["empty"] + summary["failed"],
            summary["attempted"],
        )
        self.assertEqual(summary["results"][0]["rows"], 10)
        self.assertEqual(summary["results"][0]["latest_date"], "2026-08-05")
        self.assertEqual(summary["results"][0]["output_path"], "data/AAPL.csv")
        self.assertIsNone(summary["results"][1]["output_path"])
        self.assertEqual(summary["results"][1]["message"], "Yahoo returned no data")
        self.assertEqual(summary["results"][2]["message"], "connection timeout")

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_empty_and_failed_results_do_not_stop_later_symbols(self, mock_download):
        self.write_universe(["AAPL", "AMD", "NVDA"])
        mock_download.side_effect = [
            self.download_result("AAPL", "empty", "empty"),
            self.download_result("AMD", "failed", "failed"),
            self.download_result("NVDA"),
        ]
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        self.assertEqual(mock_download.call_count, 3)
        self.assertEqual(report["download_summary"]["successful_symbols"], ["NVDA"])

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_raised_exception_becomes_failed_and_does_not_stop(self, mock_download):
        self.write_universe(["AAPL", "AMD"])
        mock_download.side_effect = [RuntimeError("socket closed"), self.download_result("AMD")]
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        summary = report["download_summary"]
        self.assertEqual(mock_download.call_count, 2)
        self.assertEqual(summary["failed_symbols"], ["AAPL"])
        self.assertEqual(summary["successful_symbols"], ["AMD"])
        self.assertIn("socket closed", summary["results"][0]["message"])

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_malformed_results_are_failed_with_warnings(self, mock_download):
        malformed = [
            None,
            "not-a-dict",
            {"symbol": "AAPL"},
            {"symbol": "AAPL", "status": "unknown"},
            {"status": "success", "rows": 1, "output_path": "data/AAPL.csv"},
            {"symbol": "AAPL", "status": "success", "rows": 0, "output_path": "data/AAPL.csv"},
        ]
        for raw_result in malformed:
            with self.subTest(raw_result=raw_result):
                self.write_universe(["AAPL"])
                mock_download.reset_mock()
                mock_download.return_value = raw_result
                report = universe_scale_test.run_scale_validation(
                    self.universe_path, self.data_dir, download=True
                )
                summary = report["download_summary"]
                self.assertEqual(summary["failed"], 1)
                self.assertEqual(summary["failed_symbols"], ["AAPL"])
                self.assertEqual(summary["results"][0]["status"], "failed")
                self.assertTrue(report["warnings"])

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_existing_valid_files_are_skipped(self, mock_download):
        self.write_universe(["AAPL", "AMD"])
        self.write_data("AAPL", {"Date": ["2026-08-05"], "Close": [1.0]})
        self.write_data("AMD", {"Date": ["2026-08-05"], "Close": [2.0]})
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        mock_download.assert_not_called()
        self.assertEqual(report["valid_files"], 2)
        self.assertEqual(report["download_summary"]["skipped"], 2)

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_success_status_is_preserved_when_post_download_file_is_invalid(self, mock_download):
        self.write_universe(["AAPL"])
        mock_download.return_value = self.download_result("AAPL")
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        self.assertEqual(report["download_summary"]["results"][0]["status"], "success")
        self.assertEqual(report["valid_files"], 0)
        self.assertTrue(
            any("local data validation failed" in item for item in report["warnings"])
        )

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_file_before_and_after_metadata_is_recorded(self, mock_download):
        self.write_universe(["AAPL", "AMD"])
        existing = self.write_data(
            "AAPL", {"Date": ["2026-08-05"], "Close": [1.0]}
        )
        before_bytes = existing.stat().st_size

        def download(symbol):
            if symbol == "AMD":
                self.write_data("AMD", {"Date": ["2026-08-05"], "Close": [2.0]})
            return self.download_result(symbol)

        mock_download.side_effect = download
        report = universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True
        )
        result = report["download_summary"]["results"][0]
        mock_download.assert_called_once_with("AMD")
        self.assertEqual(existing.stat().st_size, before_bytes)
        self.assertFalse(result["file_existed_before"])
        self.assertIsNone(result["bytes_before"])
        self.assertTrue(result["file_exists_after"])
        self.assertGreater(result["bytes_after"], 0)

    @patch("universe_scale_test.update_data.update_one_stock")
    def test_download_limit_selects_first_missing_symbols(self, mock_download):
        self.write_universe(["AAPL", "AMD", "NVDA"])
        self.write_data("AAPL", {"Date": ["2026-08-05"], "Close": [1.0]})
        mock_download.return_value = self.download_result("AMD")
        universe_scale_test.run_scale_validation(
            self.universe_path, self.data_dir, download=True, limit=1
        )
        mock_download.assert_called_once_with("AMD")

    def test_inspection_reports_rows_dates_and_sizes(self):
        path = self.write_data(
            "AAPL", {"Date": ["2026-08-01", "2026-08-05"], "Close": [1, 2]}
        )
        report = universe_scale_test.inspect_local_data(["AAPL"], self.data_dir)
        self.assertEqual(report["row_counts"], {"AAPL": 2})
        self.assertEqual(report["first_dates"], {"AAPL": "2026-08-01"})
        self.assertEqual(report["file_sizes"], {"AAPL": path.stat().st_size})

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
        self.assertEqual(
            report["download_summary"],
            universe_scale_test._empty_download_summary(),
        )
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

    @patch("universe_scale_test.run_scale_validation")
    def test_cli_download_limit_five_is_forwarded(self, mock_run):
        mock_run.return_value = self.report_fixture(download=True)
        self.assertEqual(
            universe_scale_test.main(["--download", "--limit", "5"]), 0
        )
        self.assertTrue(mock_run.call_args.kwargs["download"])
        self.assertEqual(mock_run.call_args.kwargs["limit"], 5)

    @patch("builtins.print")
    def test_cli_output_includes_all_status_totals_without_traceback(self, mock_print):
        report = self.report_fixture(download=True)
        report["download_summary"].update(
            {"attempted": 1, "failed": 1, "failed_symbols": ["AAPL"]}
        )
        report["download_summary"]["results"] = [
            {
                **self.download_result("AAPL", "failed", "timeout"),
                "elapsed_seconds": 0.1,
                "file_existed_before": False,
                "file_exists_after": False,
                "bytes_before": None,
                "bytes_after": None,
            }
        ]
        universe_scale_test._print_summary(report)
        output = "\n".join(str(item.args[0]) for item in mock_print.call_args_list if item.args)
        self.assertIn("Succeeded: 0", output)
        self.assertIn("Empty: 0", output)
        self.assertIn("Failed: 1", output)
        self.assertNotIn("Traceback", output)

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
                "empty": 0,
                "failed": 0,
                "successful_symbols": [],
                "empty_symbols": [],
                "failed_symbols": [],
                "results": [],
                "elapsed_seconds": 0.0,
                "average_seconds_per_symbol": 0.0,
            },
            "warnings": [],
        }


if __name__ == "__main__":
    unittest.main()
