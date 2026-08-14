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

    def generate(
        self,
        report_data=None,
        summary_side_effect=None,
        profiles=None,
        profile_side_effect=None,
    ):
        report_data = self.report_data if report_data is None else report_data
        if profiles is None:
            profiles = pd.DataFrame(columns=["ticker"])

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
                mock.patch.object(
                    report_terminal,
                    "load_company_profiles",
                    return_value=profiles,
                    side_effect=profile_side_effect,
                ) as profile_loader,
            ):
                generated_path = report_terminal.generate_terminal_report()

            self.assertEqual(generated_path, output_path)
            self.assertTrue(output_path.exists())
            html = output_path.read_text(encoding="utf-8")
        return html, summary_builder, profile_loader

    def test_terminal_report_contains_sections_and_research_card(self):
        html, summary_builder, _ = self.generate()

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

    def test_terminal_discloses_partial_readiness_counts(self):
        context = {
            "ConfiguredUniverseCount": 150, "ResearchReadyCount": 143,
            "ExcludedUniverseCount": 7, "ProviderRejectedCount": 5,
            "StaleMarketDataCount": 0, "InsufficientHistoryCount": 2,
        }
        with mock.patch.object(report_terminal, "load_readiness_context", return_value=context):
            html = report_terminal.build_html(self.report_data)
        for value in ("Configured Universe", "150", "Research Ready", "143", "Excluded", "7", "Provider Rejected", "5", "Stale Market Data", "Insufficient History", "2"):
            self.assertIn(value, html)

    def test_combined_score_is_formatted_to_two_decimal_places(self):
        html, _, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)

    def test_numeric_string_combined_score_is_formatted(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame([{"Ticker": "GOOGL", "CombinedScore": "76.62"}]),
        )
        html, _, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)

    def test_missing_score_displays_na(self):
        self.report_data[0][1].loc[0, "CombinedScore"] = None
        self.report_data[3][1].loc[0, "CombinedScore"] = float("nan")
        html, _, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> N/A", html)

    def test_score_falls_back_to_combined_score_section(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame([{"Ticker": "GOOGL", "FinalScore": 80}]),
        )
        html, _, _ = self.generate()
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)

    def test_empty_ticker_has_no_card_link_or_summary_call(self):
        self.report_data[0] = (
            "Top Opportunities",
            pd.DataFrame([{"Ticker": "  ", "CombinedScore": 76.62}]),
        )
        html, summary_builder, _ = self.generate()
        self.assertNotIn("cards/.html", html)
        summary_builder.assert_not_called()
        self.assertIn("Top Opportunities", html)

    def test_summary_html_is_escaped(self):
        unsafe = "<script>alert(1)</script>"
        self.summary["summary"] = unsafe
        html, _, _ = self.generate()
        self.assertNotIn(unsafe, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_summary_exception_does_not_stop_terminal_generation(self):
        html, _, _ = self.generate(summary_side_effect=RuntimeError("unavailable"))
        self.assertIn("INSUFFICIENT DATA", html)
        self.assertIn("Research summary is unavailable for this symbol.", html)
        self.assertIn("Model Portfolio", html)
        self.assertIn(
            '<div class="metric-value metric-insufficient">1</div>',
            html,
        )

    def test_terminal_uses_project_version(self):
        html, _, _ = self.generate()
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
        html, _, _ = self.generate()
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
        html, summary_builder, _ = self.generate()
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
        html, _, _ = self.generate()
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

    def test_top_opportunity_displays_investment_profile(self):
        profiles = pd.DataFrame(
            [
                {
                    "ticker": "GOOGL",
                    "company": "Alphabet Inc.",
                    "investment_stage": "MATURE",
                    "moat_score": 5,
                    "investor_rating": 90,
                    "investment_thesis": "AI and cloud platform opportunity.",
                    "risk_factor": "Regulatory and competitive pressure.",
                }
            ]
        )

        html, _, profile_loader = self.generate(profiles=profiles)

        for expected in (
            "Long-Term Context",
            "Alphabet Inc.",
            "Investment Stage:</strong> MATURE",
            "Moat Score:</strong> 5",
            "Investor Rating:</strong> 90",
            "AI and cloud platform opportunity.",
            "Regulatory and competitive pressure.",
            "Qualitative context only; not used in score or stance.",
        ):
            self.assertIn(expected, html)
        profile_loader.assert_called_once_with()

    def test_missing_profile_displays_unavailable(self):
        profiles = pd.DataFrame([{"ticker": "MSFT", "company": "Microsoft"}])
        html, _, _ = self.generate(profiles=profiles)

        self.assertIn("Investment Profile unavailable.", html)
        self.assertIn("<strong>Combined Score:</strong> 76.62", html)
        self.assertIn("GOOGL deterministic research summary.", html)

    def test_missing_profile_file_does_not_stop_terminal(self):
        html, _, _ = self.generate(profile_side_effect=FileNotFoundError("missing"))

        self.assertIn("Investment Profile unavailable.", html)
        self.assertIn("Model Portfolio", html)
        self.assertIn("BUY CANDIDATE", html)

    def test_invalid_profile_data_does_not_stop_terminal(self):
        html, _, _ = self.generate(profile_side_effect=ValueError("invalid"))

        self.assertIn("Investment Profile unavailable.", html)
        self.assertIn("Combined Score", html)
        self.assertIn('href="cards/GOOGL.html"', html)

    def test_profile_html_is_escaped(self):
        unsafe = "<script>alert(1)</script>"
        profiles = pd.DataFrame(
            [
                {
                    "ticker": "GOOGL",
                    "company": unsafe,
                    "investment_stage": "MATURE",
                    "moat_score": 5,
                    "investor_rating": 90,
                    "investment_thesis": unsafe,
                    "risk_factor": unsafe,
                }
            ]
        )

        html, _, _ = self.generate(profiles=profiles)

        self.assertNotIn(unsafe, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_profile_long_text_is_truncated(self):
        long_text = "Long-term platform opportunity " * 12
        profiles = pd.DataFrame(
            [
                {
                    "ticker": "GOOGL",
                    "company": "Alphabet Inc.",
                    "investment_stage": "MATURE",
                    "moat_score": 5,
                    "investor_rating": 90,
                    "investment_thesis": long_text,
                    "risk_factor": long_text,
                }
            ]
        )

        html, _, _ = self.generate(profiles=profiles)

        self.assertNotIn(long_text, html)
        self.assertGreaterEqual(html.count("…"), 2)

    def test_profile_does_not_change_quantitative_output(self):
        profiles = pd.DataFrame(
            [
                {
                    "ticker": "GOOGL",
                    "company": "Alphabet Inc.",
                    "investment_stage": "MATURE",
                    "moat_score": 5,
                    "investor_rating": 90,
                    "investment_thesis": "Long-term thesis.",
                    "risk_factor": "Long-term risk.",
                }
            ]
        )

        with_profile, _, _ = self.generate(profiles=profiles)
        without_profile, _, _ = self.generate()

        unchanged_fragments = (
            "<strong>Combined Score:</strong> 76.62",
            "BUY CANDIDATE",
            "GOOGL deterministic research summary.",
            'href="cards/GOOGL.html"',
            '<div class="metric-value metric-buy">1</div>',
        )
        for fragment in unchanged_fragments:
            self.assertIn(fragment, with_profile)
            self.assertIn(fragment, without_profile)

    def test_profile_loader_is_called_once_for_multiple_tickers(self):
        report_data = [
            (
                "Top Opportunities",
                pd.DataFrame(
                    [
                        {"Ticker": "GOOGL", "CombinedScore": 76.62},
                        {"Ticker": "MSFT", "CombinedScore": 75.00},
                    ]
                ),
            ),
            ("Model Portfolio", pd.DataFrame(columns=["Ticker"])),
            ("Order Review", pd.DataFrame(columns=["Ticker"])),
            ("Combined Score", pd.DataFrame(columns=["Ticker", "CombinedScore"])),
        ]
        profiles = pd.DataFrame(
            [
                {"ticker": "GOOGL", "company": "Alphabet Inc."},
                {"ticker": "MSFT", "company": "Microsoft Corporation"},
            ]
        )

        html, summary_builder, profile_loader = self.generate(
            report_data=report_data,
            profiles=profiles,
        )

        profile_loader.assert_called_once_with()
        self.assertEqual(summary_builder.call_count, 2)
        self.assertIn("Alphabet Inc.", html)
        self.assertIn("Microsoft Corporation", html)


if __name__ == "__main__":
    unittest.main()
