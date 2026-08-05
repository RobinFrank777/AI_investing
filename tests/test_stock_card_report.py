import tempfile
import unittest
from pathlib import Path
from unittest import mock

import stock_card_report


class StockCardReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_directory.name)
        self.cards_dir = self.temp_path / "reports" / "cards"

        self.stock_card = {
            "symbol": "GOOGL",
            "top_opportunity": {"Ticker": "GOOGL", "TradeSignal": "BUY"},
            "combined_score": {"Ticker": "GOOGL", "CombinedScore": 76.62},
            "model_portfolio": {"Ticker": "GOOGL", "PortfolioRole": "candidate"},
            "order_review": {"Ticker": "GOOGL", "ReviewStatus": "PASS"},
        }

        self.cards_patch = mock.patch.object(
            stock_card_report,
            "CARDS_DIR",
            self.cards_dir,
        )
        self.builder_patch = mock.patch.object(
            stock_card_report,
            "build_stock_card",
            return_value=self.stock_card,
        )
        self.mock_builder = self.builder_patch.start()
        self.cards_patch.start()

    def tearDown(self):
        self.builder_patch.stop()
        self.cards_patch.stop()
        self.temp_directory.cleanup()

    def read_report(self, path):
        return path.read_text(encoding="utf-8")

    def test_generates_googl_report_with_required_content(self):
        output_path = stock_card_report.generate_stock_card_report("GOOGL")

        self.assertIsInstance(output_path, Path)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "GOOGL.html")
        html = self.read_report(output_path)
        for expected in (
            "GOOGL Stock Research Card",
            "Combined Score",
            "Model Portfolio",
            "Order Review",
            "Research use only",
        ):
            self.assertIn(expected, html)

    def test_normalizes_lowercase_symbol_with_spaces(self):
        output_path = stock_card_report.generate_stock_card_report(" googl ")

        self.assertEqual(output_path.name, "GOOGL.html")
        self.mock_builder.assert_called_once_with("GOOGL")

    def test_none_section_shows_message_and_keeps_other_sections(self):
        self.stock_card["top_opportunity"] = None

        output_path = stock_card_report.generate_stock_card_report("GOOGL")
        html = self.read_report(output_path)

        self.assertIn("No matching Top Opportunity record.", html)
        self.assertIn("CombinedScore", html)
        self.assertIn("PortfolioRole", html)
        self.assertIn("ReviewStatus", html)

    def test_missing_field_values_display_na(self):
        self.stock_card["combined_score"] = {
            "NoneValue": None,
            "EmptyValue": "",
            "NaNValue": float("nan"),
        }

        output_path = stock_card_report.generate_stock_card_report("GOOGL")
        html = self.read_report(output_path)

        self.assertEqual(html.count(">N/A</td>"), 3)

    def test_html_special_characters_are_escaped(self):
        unsafe_value = "<script>alert(1)</script>"
        self.stock_card["order_review"] = {"ReviewReason": unsafe_value}

        output_path = stock_card_report.generate_stock_card_report("GOOGL")
        html = self.read_report(output_path)

        self.assertNotIn(unsafe_value, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_empty_symbol_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            stock_card_report.generate_stock_card_report("   ")

    def test_missing_output_directory_is_created(self):
        self.assertFalse(self.cards_dir.exists())

        output_path = stock_card_report.generate_stock_card_report("GOOGL")

        self.assertTrue(self.cards_dir.is_dir())
        self.assertTrue(output_path.exists())

    def test_missing_template_raises_file_not_found_error(self):
        missing_template = self.temp_path / "missing" / "stock_card.html"
        with mock.patch.object(stock_card_report, "TEMPLATE_PATH", missing_template):
            with self.assertRaises(FileNotFoundError):
                stock_card_report.generate_stock_card_report("GOOGL")


if __name__ == "__main__":
    unittest.main()
