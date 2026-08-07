import tempfile
import unittest
from pathlib import Path

import pandas as pd

import data_readiness
from universe_loader import REQUIRED_COLUMNS


def universe_frame(symbols, statuses=None):
    statuses = statuses or ["ACTIVE"] * len(symbols)
    rows = []
    for index, (ticker, status) in enumerate(zip(symbols, statuses), start=1):
        rows.append(
            {
                "order": index,
                "ticker": ticker,
                "company": f"Company {ticker}",
                "sector": "Technology",
                "industry": "Software",
                "theme": "Research",
                "layer": "A",
                "priority": index,
                "status": status,
                "asset_type": "Equity",
                "notes": "",
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def price_frame(rows=252):
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows, freq="B"),
            "Close": range(rows),
            "High": range(rows),
            "Low": range(rows),
            "Open": range(rows),
            "Volume": [1_000_000] * rows,
        }
    )


class DataReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()

    def write_universe(self, symbols, statuses=None):
        path = self.root / "universe.csv"
        universe_frame(symbols, statuses).to_csv(path, index=False)
        return path

    def write_prices(self, ticker, frame):
        path = self.data_dir / f"{ticker}.csv"
        frame.to_csv(path, index=False)
        return path

    def test_normal_data_is_ready(self):
        universe_path = self.write_universe(["GOOD"])
        self.write_prices("GOOD", price_frame(252))
        result = data_readiness.build_data_readiness(universe_path, self.data_dir)
        row = result.iloc[0]
        self.assertTrue(row["FileExists"])
        self.assertTrue(row["RequiredColumnsPresent"])
        self.assertEqual(row["HistoryRows"], 252)
        self.assertTrue(row["HistorySufficient"])
        self.assertTrue(row["Ready"])
        self.assertEqual(row["Error"], "")

    def test_missing_file_is_not_ready(self):
        result = data_readiness.build_data_readiness(
            self.write_universe(["MISSING"]), self.data_dir
        )
        row = result.iloc[0]
        self.assertFalse(row["FileExists"])
        self.assertFalse(row["Ready"])
        self.assertEqual(row["Error"], "Price file not found")

    def test_missing_field_is_not_ready(self):
        universe_path = self.write_universe(["FIELDS"])
        self.write_prices("FIELDS", price_frame().drop(columns=["Volume"]))
        row = data_readiness.build_data_readiness(universe_path, self.data_dir).iloc[0]
        self.assertFalse(row["RequiredColumnsPresent"])
        self.assertEqual(row["MissingColumns"], "Volume")
        self.assertFalse(row["Ready"])
        self.assertEqual(row["Error"], "Missing required columns")

    def test_insufficient_history_is_not_ready(self):
        universe_path = self.write_universe(["SHORT"])
        self.write_prices("SHORT", price_frame(251))
        row = data_readiness.build_data_readiness(universe_path, self.data_dir).iloc[0]
        self.assertEqual(row["HistoryRows"], 251)
        self.assertFalse(row["HistorySufficient"])
        self.assertFalse(row["Ready"])
        self.assertEqual(row["Error"], "Insufficient history")

    def test_only_active_symbols_are_checked(self):
        universe_path = self.write_universe(["ACTIVE1", "WATCH1"], ["ACTIVE", "WATCH"])
        self.write_prices("ACTIVE1", price_frame())
        result = data_readiness.build_data_readiness(universe_path, self.data_dir)
        self.assertEqual(result["Ticker"].tolist(), ["ACTIVE1"])

    def test_output_is_saved_without_index(self):
        universe_path = self.write_universe(["GOOD"])
        self.write_prices("GOOD", price_frame())
        output_path = self.root / "results" / "readiness.csv"
        result = data_readiness.run_data_readiness(
            universe_path, self.data_dir, output_path
        )
        self.assertEqual(result["output_path"], str(output_path))
        saved = pd.read_csv(output_path)
        self.assertEqual(saved.columns.tolist(), list(data_readiness.READINESS_COLUMNS))
        self.assertEqual(saved["Ticker"].tolist(), ["GOOD"])


if __name__ == "__main__":
    unittest.main()
