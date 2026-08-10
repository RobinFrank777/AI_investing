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
        self.research_summary = {
            "symbol": "GOOGL",
            "project_version": "v3.3.1",
            "stance": "BUY CANDIDATE",
            "strengths": [
                "Combined score is strong.",
                "Order review passed the current system checks.",
            ],
            "risks": [
                "The stock is not included in the current Top Opportunities list."
            ],
            "summary": (
                "GOOGL is classified as a BUY CANDIDATE for research review only."
            ),
            "manual_review_required": True,
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
        self.summary_patch = mock.patch.object(
            stock_card_report,
            "build_research_summary",
            return_value=self.research_summary,
        )
        self.mock_builder = self.builder_patch.start()
        self.mock_summary_builder = self.summary_patch.start()
        self.cards_patch.start()

    def tearDown(self):
        self.summary_patch.stop()
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
            "Top Opportunity",
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
        self.mock_summary_builder.assert_called_once_with("GOOGL")

    def test_displays_research_summary(self):
        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )

        for expected in (
            "Research Summary",
            "BUY CANDIDATE",
            "Combined score is strong.",
            "Order review passed",
            "Top Opportunities",
            "research review only",
            "Manual review is required before any real trade.",
            "v3.3.1",
        ):
            self.assertIn(expected, html)

    def test_displays_valid_investment_profile(self):
        self.stock_card["investment_profile"] = {
            "company_name": "Alphabet",
            "business_model": "Digital advertising and cloud services",
            "investment_thesis": "AI and cloud growth",
            "moat_score": 5,
            "growth_driver": "AI adoption",
            "risk_factor": "Regulation",
            "investment_stage": "MATURE",
            "investor_rating": 90,
        }

        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )

        for expected in (
            "Investment Profile",
            "Alphabet",
            "Digital advertising and cloud services",
            "AI and cloud growth",
            "Moat Score:</strong> 5",
            "AI adoption",
            "Regulation",
            "MATURE",
            "Investor Rating:</strong> 90",
        ):
            self.assertIn(expected, html)

    def test_unavailable_profile_does_not_break_report(self):
        self.stock_card["investment_profile"] = None

        output_path = stock_card_report.generate_stock_card_report("GOOGL")
        html = self.read_report(output_path)

        self.assertTrue(output_path.exists())
        self.assertIn("Investment Profile unavailable.", html)
        self.assertIn("Combined Score", html)

    def test_empty_strengths_show_explanation(self):
        self.research_summary["strengths"] = []
        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )
        self.assertIn("No identified strengths from the current rules.", html)

    def test_empty_risks_show_explanation(self):
        self.research_summary["risks"] = []
        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )
        self.assertIn(
            "No additional rule-based risks were identified.",
            html,
        )

    def test_research_summary_special_characters_are_escaped(self):
        unsafe_value = "<script>alert(1)</script>"
        self.research_summary.update(
            stance=unsafe_value,
            strengths=[unsafe_value],
            risks=[unsafe_value],
            summary=unsafe_value,
            project_version=unsafe_value,
        )

        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )

        self.assertNotIn(unsafe_value, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_empty_research_summary_values_display_na(self):
        self.research_summary.update(
            stance=None,
            summary="",
            project_version=None,
        )

        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )

        self.assertGreaterEqual(html.count("N/A"), 3)

    def test_manual_review_true_displays_warning(self):
        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )
        self.assertIn("Manual review is required before any real trade.", html)

    def test_manual_review_false_omits_warning(self):
        self.research_summary["manual_review_required"] = False
        html = self.read_report(
            stock_card_report.generate_stock_card_report("GOOGL")
        )
        self.assertNotIn("Manual review is required before any real trade.", html)
        self.assertIn("Research Summary", html)

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
