import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import update_data


class UpdateOneStockTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data_dir = Path(self.directory.name)
        self.data_dir_patch = patch("update_data.DATA_DIR", self.data_dir)
        self.data_dir_patch.start()
        self.addCleanup(self.data_dir_patch.stop)

    @staticmethod
    def market_data():
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1100],
            },
            index=pd.DatetimeIndex(["2026-08-04", "2026-08-05"]),
        )

    @patch("update_data.yf.download")
    def test_success_contract_rows_latest_date_and_output_path(self, mock_download):
        mock_download.return_value = self.market_data()

        result = update_data.update_one_stock("AAPL")

        self.assertEqual(
            result,
            {
                "symbol": "AAPL",
                "status": "success",
                "rows": 2,
                "latest_date": "2026-08-05",
                "output_path": str(self.data_dir / "AAPL.csv"),
                "message": "",
            },
        )
        self.assertTrue((self.data_dir / "AAPL.csv").is_file())

    @patch("update_data.yf.download", return_value=pd.DataFrame())
    def test_empty_contract_does_not_write_csv(self, _):
        result = update_data.update_one_stock("EMPTY")

        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["rows"], 0)
        self.assertIsNone(result["latest_date"])
        self.assertTrue(result["message"])
        self.assertFalse((self.data_dir / "EMPTY.csv").exists())

    @patch("update_data.yf.download", side_effect=RuntimeError("Connection timeout"))
    def test_download_exception_returns_failed_contract(self, _):
        result = update_data.update_one_stock("AAPL")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["rows"], 0)
        self.assertIsNone(result["latest_date"])
        self.assertIn("Connection timeout", result["message"])

    @patch("update_data.yf.download")
    @patch("pandas.DataFrame.to_csv", side_effect=OSError("disk full"))
    def test_csv_write_failure_returns_failed_contract(self, _, mock_download):
        mock_download.return_value = self.market_data()

        result = update_data.update_one_stock("AAPL")

        self.assertEqual(result["status"], "failed")
        self.assertIn("disk full", result["message"])

    @patch("update_data.yf.download")
    def test_only_allowed_status_values_are_returned(self, mock_download):
        mock_download.return_value = self.market_data()
        success = update_data.update_one_stock("SUCCESS")
        mock_download.return_value = pd.DataFrame()
        empty = update_data.update_one_stock("EMPTY")
        mock_download.side_effect = ValueError("bad response")
        failed = update_data.update_one_stock("FAILED")

        self.assertEqual(
            {success["status"], empty["status"], failed["status"]},
            {"success", "empty", "failed"},
        )

    @patch("update_data.yf.download")
    def test_download_call_arguments_are_unchanged(self, mock_download):
        mock_download.return_value = self.market_data()
        update_data.update_one_stock("AAPL")
        mock_download.assert_called_once_with(
            "AAPL",
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False,
        )


if __name__ == "__main__":
    unittest.main()
