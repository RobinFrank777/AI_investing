import tempfile
import unittest
from pathlib import Path
from unittest import mock

import generate_stock_cards


class GenerateStockCardsTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_directory.name)
        self.top10_path = self.temp_path / "results" / "top10.csv"
        self.cards_dir = self.temp_path / "reports" / "cards"
        self.top10_path.parent.mkdir()

        self.top10_patch = mock.patch.object(
            generate_stock_cards,
            "TOP10_PATH",
            self.top10_path,
        )
        self.cards_patch = mock.patch.object(
            generate_stock_cards,
            "CARDS_DIR",
            self.cards_dir,
        )
        self.generator_patch = mock.patch.object(
            generate_stock_cards,
            "generate_stock_card_report",
            side_effect=self.generate_card,
        )
        self.mock_generator = self.generator_patch.start()
        self.cards_patch.start()
        self.top10_patch.start()

    def tearDown(self):
        self.generator_patch.stop()
        self.cards_patch.stop()
        self.top10_patch.stop()
        self.temp_directory.cleanup()

    def generate_card(self, symbol):
        path = self.cards_dir / f"{symbol}.html"
        path.write_text(symbol, encoding="utf-8")
        return path

    def write_top10(self, content):
        self.top10_path.write_text(content, encoding="utf-8")

    def test_generates_one_card_for_each_top10_ticker(self):
        self.write_top10("Ticker,Score\nNVDA,90\nAMD,85\n")

        paths = generate_stock_cards.generate_all_stock_cards()

        self.assertEqual(len(paths), 2)
        self.assertEqual([path.name for path in paths], ["NVDA.html", "AMD.html"])
        self.assertEqual(
            self.mock_generator.call_args_list,
            [mock.call("NVDA"), mock.call("AMD")],
        )

    def test_missing_top10_csv_raises_file_not_found_error(self):
        with self.assertRaises(FileNotFoundError):
            generate_stock_cards.generate_all_stock_cards()

    def test_csv_without_ticker_column_raises_value_error(self):
        self.write_top10("Symbol,Score\nNVDA,90\n")

        with self.assertRaisesRegex(ValueError, "Ticker column"):
            generate_stock_cards.generate_all_stock_cards()

    def test_lowercase_ticker_generates_uppercase_filename(self):
        self.write_top10("Ticker\nnvda\n")

        paths = generate_stock_cards.generate_all_stock_cards()

        self.assertEqual(paths[0].name, "NVDA.html")
        self.mock_generator.assert_called_once_with("NVDA")

    def test_empty_csv_returns_empty_list(self):
        self.write_top10("Ticker\n")

        paths = generate_stock_cards.generate_all_stock_cards()

        self.assertEqual(paths, [])
        self.mock_generator.assert_not_called()
        self.assertTrue(self.cards_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
