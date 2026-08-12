import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import stock_loader


class StockLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.data_dir = Path(self.temp_directory.name)
        self.data_dir_patch = mock.patch.object(
            stock_loader, "DATA_DIR_PATH", self.data_dir
        )
        self.data_dir_patch.start()
        self.addCleanup(self.data_dir_patch.stop)

    def write_stock(self, data, ticker="TEST"):
        path = self.data_dir / f"{ticker}.csv"
        pd.DataFrame(data).to_csv(path, index=False)
        return path

    @staticmethod
    def valid_data():
        return {
            "Date": ["2026-08-04", "2026-08-05"],
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1_000, 1_100],
        }

    def test_loads_canonical_ohlcv_without_dropping_or_swapping_rows(self):
        self.write_stock(self.valid_data())

        loaded = stock_loader.load_stock("TEST")

        self.assertEqual(len(loaded), 2)
        self.assertEqual(
            loaded.columns.tolist(),
            ["Date", "Open", "High", "Low", "Close", "Volume"],
        )
        self.assertEqual(loaded.iloc[0]["Date"], "2026-08-04")
        self.assertEqual(loaded.iloc[0]["Open"], 100.0)
        self.assertEqual(loaded.iloc[0]["Close"], 101.0)

    def test_reads_by_column_name_when_source_order_changes(self):
        data = pd.DataFrame(self.valid_data())
        self.write_stock(
            data.loc[:, ["Volume", "Close", "Low", "Date", "High", "Open"]]
        )

        loaded = stock_loader.load_stock("TEST")

        self.assertEqual(loaded.columns.tolist(), stock_loader.REQUIRED_COLUMNS)
        self.assertEqual(loaded.iloc[1]["Open"], 101.0)
        self.assertEqual(loaded.iloc[1]["Close"], 102.0)

    def test_missing_required_column_is_rejected(self):
        data = self.valid_data()
        del data["Volume"]
        self.write_stock(data)

        with self.assertRaisesRegex(ValueError, "missing required columns.*Volume"):
            stock_loader.load_stock("TEST")

    def test_duplicate_dates_are_rejected(self):
        data = self.valid_data()
        data["Date"] = ["2026-08-04", "2026-08-04"]
        self.write_stock(data)

        with self.assertRaisesRegex(ValueError, "duplicate dates"):
            stock_loader.load_stock("TEST")

    def test_decreasing_dates_are_rejected(self):
        data = self.valid_data()
        data["Date"] = list(reversed(data["Date"]))
        self.write_stock(data)

        with self.assertRaisesRegex(ValueError, "dates must be increasing"):
            stock_loader.load_stock("TEST")

    def test_non_finite_numeric_value_is_rejected(self):
        data = self.valid_data()
        data["Close"][1] = float("inf")
        self.write_stock(data)

        with self.assertRaisesRegex(ValueError, "invalid numeric values"):
            stock_loader.load_stock("TEST")

    def test_invalid_ohlc_relationship_is_rejected(self):
        data = self.valid_data()
        data["High"][1] = 99.0
        self.write_stock(data)

        with self.assertRaisesRegex(ValueError, "violates OHLC"):
            stock_loader.load_stock("TEST")


if __name__ == "__main__":
    unittest.main()
