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

    @patch("update_data.completed_daily_bars")
    @patch("update_data.yf.download")
    def test_downloader_saves_only_completed_daily_bars(
        self, mock_download, mock_completed
    ):
        raw = self.market_data()
        mock_download.return_value = raw
        mock_completed.return_value = raw.iloc[:1]

        result = update_data.update_one_stock("AAPL")

        mock_completed.assert_called_once()
        self.assertEqual(result["rows"], 1)
        self.assertEqual(result["latest_date"], "2026-08-04")

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

    def test_observed_provider_invalid_rows_are_rejected(self):
        observed = {
            "KR": (56.520000, 57.535000, 56.564999, 57.230000),
            "DKS": (204.500000, 203.869995, 200.009995, 202.259995),
            "ETN": (459.309998, 459.059998, 452.500000, 453.329987),
            "LMT": (609.780029, 609.549988, 596.479980, 598.010010),
            "SPIR": (13.165000, 14.660800, 13.250000, 13.940000),
        }
        for ticker, values in observed.items():
            with self.subTest(ticker=ticker), patch("update_data.yf.download") as download:
                frame = self.market_data().iloc[[0]].copy()
                extra = pd.DataFrame(
                    {"Open": [values[0]], "High": [values[1]], "Low": [values[2]],
                     "Close": [values[3]], "Volume": [1000]},
                    index=pd.DatetimeIndex(["2026-08-13"]),
                )
                download.return_value = pd.concat([frame, extra])
                result = update_data.update_one_stock(ticker)
                saved = pd.read_csv(self.data_dir / f"{ticker}.csv")
                self.assertEqual(result["status"], "provider_rejected")
                self.assertEqual(result["latest_date"], "2026-08-04")
                self.assertNotIn("2026-08-13", saved.Date.tolist())

    @patch("update_data.yf.download")
    def test_invalid_refresh_preserves_existing_valid_same_date_row(self, download):
        existing = pd.DataFrame({
            "Date": ["2026-08-13"], "Open": [100.0], "High": [102.0],
            "Low": [99.0], "Close": [101.0], "Volume": [900],
        })
        existing.to_csv(self.data_dir / "AAA.csv", index=False)
        invalid = pd.DataFrame({
            "Open": [105.0], "High": [104.0], "Low": [100.0],
            "Close": [103.0], "Volume": [1200],
        }, index=pd.DatetimeIndex(["2026-08-13"]))
        download.return_value = invalid
        result = update_data.update_one_stock("AAA")
        saved = pd.read_csv(self.data_dir / "AAA.csv")
        self.assertEqual(result["status"], "provider_rejected")
        self.assertEqual(saved.iloc[0].to_dict(), existing.iloc[0].to_dict())

    @patch("update_data.yf.download")
    def test_same_date_valid_refresh_replaces_entire_row_atomically(self, download):
        pd.DataFrame({
            "Date": ["2026-08-13"], "Open": [10.0], "High": [12.0],
            "Low": [9.0], "Close": [11.0], "Volume": [100],
        }).to_csv(self.data_dir / "AAA.csv", index=False)
        fresh = pd.DataFrame({
            "Open": [20.0], "High": [24.0], "Low": [19.0],
            "Close": [23.0], "Volume": [999],
        }, index=pd.DatetimeIndex(["2026-08-13"]))
        download.return_value = fresh
        self.assertEqual(update_data.update_one_stock("AAA")["status"], "success")
        row = pd.read_csv(self.data_dir / "AAA.csv").iloc[0]
        self.assertEqual(
            row[["Open", "High", "Low", "Close", "Volume"]].tolist(),
            [20.0, 24.0, 19.0, 23.0, 999],
        )

    def test_duplicate_date_resolution_is_deterministic_and_whole_row(self):
        frame = pd.DataFrame({
            "Date": ["2026-08-13", "2026-08-13"],
            "Open": [10.0, 20.0], "High": [12.0, 24.0],
            "Low": [9.0, 19.0], "Close": [11.0, 23.0], "Volume": [100, 999],
        })
        first, rejected = update_data.build_atomic_canonical_history(frame)
        second, _ = update_data.build_atomic_canonical_history(frame)
        pd.testing.assert_frame_equal(first, second)
        self.assertFalse(rejected)
        self.assertEqual(first.iloc[0][["Open", "High", "Low", "Close", "Volume"]].tolist(),
                         [20.0, 24.0, 19.0, 23.0, 999])

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
