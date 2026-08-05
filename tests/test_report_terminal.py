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

    def dashboard_metrics(self, items, portfolio_tickers=()):
        portfolio = pd.DataFrame({"Ticker": list(portfolio_tickers)})
        return report_terminal.build_dashboard_metrics(items, portfolio)

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
        self.assertIn(
            '<div class="metric-value metric-insufficient">1</div>',
            html,
        )

    def test_terminal_uses_project_version(self):
        html, _ = self.generate()
        self.assertIn(PROJECT_VERSION, html)
        source = Path(report_terminal.__file__).read_text(encoding="utf-8")
        self.assertNotIn('VERSION = "v3.3.0"', source)

    def test_model_portfolio_has_normalized_research_card_link(self):
        self.report_data[1] = (
            "Model Portfolio",
            pd.DataFrame(
                [{"Ticker": " googl ", "PortfolioRole": "candidate"}]
            ),
        )
        html, _ = self.generate()
        self.assertIn('href="cards/GOOGL.html"', html)
        self.assertIn("View Card", html)
        self.assertIn("PortfolioRole", html)
        self.assertIn("candidate", html)

    def test_model_portfolio_empty_ticker_has_no_empty_link(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame(columns=["Ticker", "CombinedScore"]),
        )
        self.report_data[1] = (
            "Model Portfolio",
            pd.DataFrame([{"Ticker": None, "PortfolioRole": "candidate"}]),
        )
        html, summary_builder = self.generate()
        self.assertNotIn("cards/.html", html)
        self.assertIn("PortfolioRole", html)
        summary_builder.assert_not_called()

    def test_dashboard_counts_all_stances(self):
        items = [
            {"symbol": "A", "stance": stance, "combined_score": 70}
            for stance in (
                "BUY CANDIDATE",
                "HOLD / REVIEW",
                "REDUCE / AVOID",
                "INSUFFICIENT DATA",
            )
        ]
        metrics = self.dashboard_metrics(items)

        self.assertEqual(metrics["top_opportunities_count"], 4)
        self.assertEqual(metrics["buy_candidate_count"], 1)
        self.assertEqual(metrics["hold_review_count"], 1)
        self.assertEqual(metrics["reduce_avoid_count"], 1)
        self.assertEqual(metrics["insufficient_data_count"], 1)

    def test_dashboard_average_combined_score(self):
        items = [
            {"symbol": "A", "stance": "HOLD / REVIEW", "combined_score": score}
            for score in (80, 70, "60")
        ]
        metrics = self.dashboard_metrics(items)
        self.assertEqual(metrics["average_combined_score"], "70.00")

    def test_dashboard_ignores_invalid_scores(self):
        items = [
            {"symbol": symbol, "stance": "HOLD / REVIEW", "combined_score": score}
            for symbol, score in (
                ("A", 80),
                ("B", None),
                ("C", float("nan")),
                ("D", "invalid"),
            )
        ]
        metrics = self.dashboard_metrics(items)
        self.assertEqual(metrics["average_combined_score"], "80.00")
        self.assertEqual(metrics["highest_score"], "A / 80.00")

    def test_dashboard_highest_score_uses_first_ticker_on_tie(self):
        items = [
            {"symbol": "FIRST", "stance": "HOLD / REVIEW", "combined_score": 92.35},
            {"symbol": "SECOND", "stance": "HOLD / REVIEW", "combined_score": 92.35},
            {"symbol": "THIRD", "stance": "HOLD / REVIEW", "combined_score": 80},
        ]
        metrics = self.dashboard_metrics(items)
        self.assertEqual(metrics["highest_score"], "FIRST / 92.35")

    def test_empty_dashboard_metrics(self):
        metrics = self.dashboard_metrics([])
        self.assertEqual(metrics["top_opportunities_count"], 0)
        self.assertEqual(metrics["buy_candidate_count"], 0)
        self.assertEqual(metrics["hold_review_count"], 0)
        self.assertEqual(metrics["reduce_avoid_count"], 0)
        self.assertEqual(metrics["insufficient_data_count"], 0)
        self.assertEqual(metrics["average_combined_score"], "N/A")
        self.assertEqual(metrics["highest_score"], "N/A")
        self.assertEqual(metrics["research_card_link_count"], 0)

    def test_dashboard_model_portfolio_counts_only_valid_tickers(self):
        metrics = self.dashboard_metrics(
            [],
            portfolio_tickers=("GOOGL", " amd ", None, float("nan"), "  "),
        )
        self.assertEqual(metrics["model_portfolio_count"], 2)

    def test_dashboard_html_contains_all_metrics_and_original_sections(self):
        html, _ = self.generate()
        for expected in (
            "Today's Research Dashboard",
            "Pipeline Status",
            "Top Opportunities",
            "BUY CANDIDATE",
            "HOLD / REVIEW",
            "REDUCE / AVOID",
            "INSUFFICIENT DATA",
            "Average Combined Score",
            "Highest Score",
            "Model Portfolio Count",
            "Research Card Links",
            "Generated Time",
            "System Status",
            "Model Portfolio",
            "Order Review",
            "Combined Score",
        ):
            self.assertIn(expected, html)


if __name__ == "__main__":
    unittest.main()
