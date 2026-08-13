import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import universe_loader
import config


def universe_frame(size=3):
    layers = ("A", "B", "C")
    rows = []
    for index in range(size):
        rows.append(
            {
                "order": index + 1,
                "ticker": f"TEST{index:03d}",
                "company": f"Company {index}",
                "sector": "Technology",
                "industry": "Software",
                "theme": "Research",
                "layer": layers[index % len(layers)],
                "priority": index + 1,
                "status": "ACTIVE" if index % 2 == 0 else "WATCH",
                "asset_type": "Equity",
                "notes": "",
            }
        )
    return pd.DataFrame(rows, columns=universe_loader.REQUIRED_COLUMNS)


class UniverseLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_universe(self, frame, name="universe.csv"):
        path = self.root / name
        frame.to_csv(path, index=False)
        return path

    def test_load_success_with_150_rows(self):
        loaded = universe_loader.load_universe(self.write_universe(universe_frame(150)))
        self.assertIsInstance(loaded, pd.DataFrame)
        self.assertEqual(len(loaded), 150)

    def test_primary_path_and_version_contract(self):
        self.assertEqual(config.PRIMARY_UNIVERSE_PATH, config.DATA_DIR_PATH / "AI_investing_universe_150_V2.csv")
        self.assertEqual(config.PRIMARY_UNIVERSE_VERSION, "AI_investing_universe_150_V2")
        self.assertEqual(universe_loader.DEFAULT_UNIVERSE_PATH, config.PRIMARY_UNIVERSE_PATH)

    def test_load_normalizes_tickers_and_preserves_file_order(self):
        frame = universe_frame(3)
        frame["ticker"] = [" nvda ", "Aapl", " amd"]
        loaded = universe_loader.load_universe(self.write_universe(frame))
        self.assertEqual(loaded["ticker"].tolist(), ["NVDA", "AAPL", "AMD"])
        self.assertEqual(universe_loader.get_primary_tickers(loaded), ["NVDA", "AAPL", "AMD"])

    def test_primary_membership_does_not_depend_on_market_data(self):
        loaded = universe_loader.load_universe(self.write_universe(universe_frame(3)))
        self.assertEqual(len(universe_loader.get_primary_tickers(loaded)), 3)

    def test_required_columns_validation(self):
        frame = universe_frame().drop(columns=["industry"])
        with self.assertRaisesRegex(ValueError, "missing required columns: industry"):
            universe_loader.validate_universe(frame)

    def test_duplicate_ticker_rejection(self):
        frame = universe_frame()
        frame.loc[1, "ticker"] = " test000 "
        with self.assertRaisesRegex(ValueError, "duplicate ticker.*TEST000"):
            universe_loader.validate_universe(frame)

    def test_empty_ticker_rejection(self):
        frame = universe_frame()
        frame.loc[0, "ticker"] = "  "
        with self.assertRaisesRegex(ValueError, "empty ticker"):
            universe_loader.validate_universe(frame)

    def test_invalid_layer_rejection(self):
        frame = universe_frame()
        frame.loc[0, "layer"] = "D"
        with self.assertRaisesRegex(ValueError, "invalid layer.*D"):
            universe_loader.validate_universe(frame)

    def test_invalid_status_rejection(self):
        frame = universe_frame()
        frame.loc[0, "status"] = "INACTIVE"
        with self.assertRaisesRegex(ValueError, "invalid status.*INACTIVE"):
            universe_loader.validate_universe(frame)

    def test_active_symbol_extraction_preserves_order(self):
        frame = universe_frame(4)
        self.assertEqual(
            universe_loader.get_active_symbols(frame), ["TEST000", "TEST002"]
        )

    def test_summary_generation(self):
        frame = universe_frame(6)
        self.assertEqual(
            universe_loader.get_summary(frame),
            {"total": 6, "active": 3, "layer": {"A": 2, "B": 2, "C": 2}},
        )

    def test_missing_file_error_is_clear(self):
        with self.assertRaisesRegex(FileNotFoundError, "Research universe file not found"):
            universe_loader.load_universe(self.root / "missing.csv")

    def test_empty_file_rejection(self):
        path = self.root / "empty.csv"
        path.touch()
        with self.assertRaisesRegex(ValueError, "file is empty"):
            universe_loader.load_universe(path)

    def test_header_only_file_rejection(self):
        path = self.write_universe(universe_frame(0))
        with self.assertRaisesRegex(ValueError, "contains no rows"):
            universe_loader.load_universe(path)

    def test_cli_success(self):
        path = self.write_universe(universe_frame(6))
        with patch.object(
            universe_loader, "DEFAULT_UNIVERSE_PATH", path
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(universe_loader.main(), 0)
        text = output.getvalue()
        self.assertIn("AI_investing Research Universe", text)
        self.assertIn("Total:\n6", text)
        self.assertIn("Active:\n3", text)


if __name__ == "__main__":
    unittest.main()
