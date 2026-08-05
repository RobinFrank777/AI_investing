import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from config import PROJECT_VERSION
import report_terminal


class ReportTerminalTests(unittest.TestCase):
    def setUp(self):
        self.report_data = [
            (
                "Top Opportunities",
                pd.DataFrame([{"Ticker": "GOOGL", "CombinedScore": 76.62}]),
            ),
            ("Model Portfolio", pd.DataFrame([{"Ticker": "GOOGL"}])),
            ("Order Review", pd.DataFrame([{"Ticker": "GOOGL"}])),
            (
                "Combined Score",
                pd.DataFrame([{"Ticker": "GOOGL", "CombinedScore": 76.62}]),
            ),
        ]
        self.summary = {
            "stance": "BUY CANDIDATE",
            "summary": "GOOGL deterministic research summary.",
        }

    def generate(self, report_data=None, summary_side_effect=None):
        report_data = self.report_data if report_data is None else report_data

        with tempfile.TemporaryDirectory() as temp_directory:
            output_path = Path(temp_directory) / "ai_terminal_report.html"
            with (
                mock.patch.object(report_terminal, "OUTPUT_PATH", output_path),
                mock.patch.object(
                    report_terminal,
                    "load_report_data",
                    return_value=report_data,
                ),
                mock.patch.object(
                    report_terminal,
                    "build_research_summary",
                    return_value=self.summary,
                    side_effect=summary_side_effect,
                ) as summary_builder,
            ):
                generated_path = report_terminal.generate_terminal_report()

            self.assertEqual(generated_path, output_path)
            self.assertTrue(output_path.exists())
            html = output_path.read_text(encoding="utf-8")
        return html, summary_builder

    def test_terminal_report_contains_sections_and_research_card(self):
        html, summary_builder = self.generate()

        self.assertIn("AI_investing Daily Research Terminal", html)
        for section in (
            "System Status",
            "Top Opportunities",
            "Model Portfolio",
            "Order Review",
            "Combined Score",
        ):
            self.assertIn(section, html)
        self.assertIn("GOOGL", html)
        self.assertIn("BUY CANDIDATE", html)
        self.assertIn("GOOGL deterministic research summary.", html)
        self.assertIn('href="cards/GOOGL.html"', html)
        self.assertIn("View Card", html)
        summary_builder.assert_called_once_with("GOOGL")

    def test_combined_score_is_formatted_to_two_decimal_places(self):
        html, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)

    def test_numeric_string_combined_score_is_formatted(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame([{"Ticker": "GOOGL", "CombinedScore": "76.62"}]),
        )
        html, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)

    def test_missing_score_displays_na(self):
        self.report_data[0][1].loc[0, "CombinedScore"] = None
        self.report_data[3][1].loc[0, "CombinedScore"] = float("nan")
        html, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> N/A", html)

    def test_score_falls_back_to_combined_score_section(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame([{"Ticker": "GOOGL", "FinalScore": 80}]),
        )
        html, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)

    def test_empty_ticker_has_no_card_link_or_summary_call(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame([{"Ticker": "  ", "CombinedScore": 76.62}]),
        )
        html, summary_builder = self.generate()
        self.assertNotIn("cards/.html", html)
        summary_builder.assert_not_called()
        self.assertIn("Top Opportunities", html)

    def test_summary_html_is_escaped(self):
        unsafe = "<script>alert(1)</script>"
        self.summary["summary"] = unsafe
        html, _ = self.generate()
        self.assertNotIn(unsafe, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_summary_exception_does_not_stop_terminal_generation(self):
        html, _ = self.generate(summary_side_effect=RuntimeError("unavailable"))
        self.assertIn("INSUFFICIENT DATA", html)
        self.assertIn("Research summary is unavailable for this symbol.", html)
        self.assertIn("Model Portfolio", html)

    def test_terminal_uses_project_version(self):
        html, _ = self.generate()
        self.assertIn(PROJECT_VERSION, html)
        source = Path(report_terminal.__file__).read_text(encoding="utf-8")
        self.assertNotIn('VERSION = "v3.3.0"', source)


if __name__ == "__main__":
    unittest.main()
