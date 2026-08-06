import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import update_data


class UpdateDataUniverseTests(unittest.TestCase):
    @patch("update_data.update_one_stock")
    @patch("update_data.load_active_universe", return_value=["AAPL", "AMD", "NVDA"])
    def test_updates_normal_universe_in_order(self, mock_load, mock_update):
        mock_update.return_value = {"status": "success"}
        result = update_data.update_all_stocks()

        self.assertEqual(
            mock_update.call_args_list,
            [call("AAPL"), call("AMD"), call("NVDA")],
        )
        self.assertEqual(result["succeeded"], 3)

    @patch("update_data.update_one_stock")
    @patch("update_data.load_active_universe", return_value=["MixedCase", " spaced "])
    def test_uses_symbols_without_additional_normalization(self, _, mock_update):
        update_data.update_all_stocks()

        self.assertEqual(
            mock_update.call_args_list,
            [call("MixedCase"), call(" spaced ")],
        )

    @patch("update_data.update_one_stock")
    @patch("update_data.load_active_universe", return_value=["AAPL", "AMD"])
    def test_loads_universe_once_per_batch(self, mock_load, _):
        update_data.update_all_stocks()
        mock_load.assert_called_once_with()

    @patch("update_data.update_one_stock")
    @patch("update_data.load_active_universe", return_value=[])
    @patch("builtins.print")
    def test_empty_universe_skips_downloads(self, mock_print, _, mock_update):
        result = update_data.update_all_stocks()

        mock_update.assert_not_called()
        self.assertEqual(
            result,
            {"total": 0, "succeeded": 0, "failed": 0, "failed_symbols": []},
        )
        mock_print.assert_called_once_with(
            "No enabled symbols found in market universe."
        )

    @patch("update_data.load_active_universe", side_effect=FileNotFoundError("missing"))
    @patch("builtins.print")
    def test_missing_universe_is_reported_and_raised(self, mock_print, _):
        with self.assertRaisesRegex(FileNotFoundError, "missing"):
            update_data.update_all_stocks()
        self.assertIn("Unable to load market universe", mock_print.call_args.args[0])

    @patch("update_data.load_active_universe", side_effect=ValueError("invalid CSV"))
    @patch("builtins.print")
    def test_invalid_universe_is_reported_and_raised(self, mock_print, _):
        with self.assertRaisesRegex(ValueError, "invalid CSV"):
            update_data.update_all_stocks()
        self.assertIn("Unable to load market universe", mock_print.call_args.args[0])

    @patch("update_data.load_active_universe", return_value=["AAPL", "AMD", "NVDA"])
    @patch("update_data.update_one_stock")
    def test_single_failure_does_not_stop_other_symbols(self, mock_update, _):
        mock_update.side_effect = [
            {"status": "success"},
            {"status": "failed", "message": "download failed"},
            {"status": "success"},
        ]

        result = update_data.update_all_stocks()

        self.assertEqual(mock_update.call_count, 3)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failed_symbols"], ["AMD"])

    @patch("update_data.load_active_universe", return_value=["AAPL", "AMD"])
    @patch("update_data.update_one_stock")
    def test_all_success_statistics(self, mock_update, _):
        mock_update.return_value = {"status": "success"}
        result = update_data.update_all_stocks()

        self.assertEqual(
            result,
            {"total": 2, "succeeded": 2, "failed": 0, "failed_symbols": []},
        )
        self.assertEqual(mock_update.call_count, 2)

    @patch("update_data.load_active_universe", return_value=["EMPTY"])
    @patch("update_data.update_one_stock", return_value={"status": "empty"})
    def test_empty_download_is_counted_as_failed(self, mock_update, _):
        result = update_data.update_all_stocks()

        self.assertEqual(
            result,
            {
                "total": 1,
                "succeeded": 0,
                "failed": 1,
                "failed_symbols": ["EMPTY"],
            },
        )
        mock_update.assert_called_once_with("EMPTY")

    @patch("update_data.yf.download")
    def test_output_path_filename_and_csv_columns_are_unchanged(self, mock_download):
        index = pd.DatetimeIndex(["2026-08-05"], name="OriginalName")
        mock_download.return_value = pd.DataFrame(
            {
                "Open": [1.0],
                "High": [2.0],
                "Low": [0.5],
                "Close": [1.5],
                "Volume": [100],
            },
            index=index,
        )

        with tempfile.TemporaryDirectory() as directory:
            with patch("update_data.DATA_DIR", Path(directory)):
                result = update_data.update_one_stock("BRK.B")
            output = Path(directory) / "BRK.B.csv"
            self.assertTrue(output.is_file())
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["output_path"], str(output))
            self.assertEqual(
                list(pd.read_csv(output).columns),
                ["Date", "Open", "High", "Low", "Close", "Volume"],
            )

        mock_download.assert_called_once_with(
            "BRK.B",
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

    @patch("update_data.update_all_stocks", return_value={})
    def test_main_success_exit_code(self, mock_update):
        self.assertEqual(update_data.main(), 0)
        mock_update.assert_called_once_with()

    @patch("update_data.update_all_stocks", side_effect=ValueError("invalid"))
    def test_main_failure_exit_code(self, _):
        self.assertEqual(update_data.main(), 1)

    @patch("update_data.load_active_universe", return_value=["AAPL"])
    def test_legacy_load_watchlist_uses_active_source(self, mock_load):
        self.assertEqual(update_data.load_watchlist(), ["AAPL"])
        mock_load.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
