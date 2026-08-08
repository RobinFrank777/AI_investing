import unittest

import pandas as pd

import ai_research_summary_builder
import candidate_report_builder
import daily_research_snapshot
import research_candidate_selector
import research_dataset_validator
import research_explanation_engine
import research_report_composer
import risk_factor_merge


class ResearchPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.factors = pd.DataFrame(
            {
                "Ticker": ["NVDA", "AMD"],
                "TrendValue": [0.9, 0.7],
                "MomentumValue": [0.8, 0.6],
                "Volatility20D": [0.2, 0.3],
                "FactorStatus": ["PASS", "PASS"],
                "FactorError": ["", ""],
            }
        )
        self.risk = pd.DataFrame(
            {
                "Ticker": ["NVDA", "AMD"],
                "AnnualizedVolatility": [0.25, 0.30],
                "MaxDrawdown": [-0.10, -0.15],
                "SharpeRatio": [1.5, 1.2],
                "ObservationCount": [300, 300],
                "Status": ["PASS", "PASS"],
            }
        )
        self.ranking = pd.DataFrame(
            {
                "Ticker": ["NVDA", "AMD"],
                "TrendScore": [0.9, 0.7],
                "MomentumScore": [0.8, 0.6],
                "LowVolScore": [0.8, 0.6],
                "CompositeScore": [0.84, 0.64],
                "Rank": [1, 2],
            }
        )
        self.signals = pd.DataFrame(
            {
                "Ticker": ["NVDA", "AMD"],
                "TrendSignal": ["STRONG", "NORMAL"],
                "MomentumSignal": ["POSITIVE", "NEUTRAL"],
                "VolatilitySignal": ["LOW", "NORMAL"],
                "CompositeSignal": ["B", "C"],
            }
        )

    def test_schema_contract_flows_from_merge_to_markdown(self):
        research = risk_factor_merge.merge_research_artifacts(
            self.factors, self.risk, self.ranking, self.signals
        )
        validation = research_dataset_validator.validate_research_data(research)
        overall = validation.set_index("CheckItem").at["OverallStatus", "Value"]
        self.assertEqual(overall, "PASS")

        candidates = research_candidate_selector.select_research_candidates(research)
        report = candidate_report_builder.build_candidate_report(
            candidates, generation_date="2026-08-08"
        )
        snapshot = daily_research_snapshot.build_daily_snapshot(
            report, generation_date="2026-08-08"
        )
        explanations = research_explanation_engine.build_research_explanations(
            snapshot
        )
        summaries = ai_research_summary_builder.build_ai_research_summaries(
            explanations
        )
        markdown = research_report_composer.compose_research_report(summaries)

        self.assertEqual(summaries["Ticker"].tolist(), ["NVDA", "AMD"])
        self.assertEqual(summaries["Signal"].tolist(), ["B", "C"])
        self.assertEqual(summaries["Rank"].tolist(), [1.0, 2.0])
        self.assertEqual(summaries["CompositeScore"].tolist(), [0.84, 0.64])
        self.assertIn("### Rank 1 - NVDA", markdown)
        self.assertIn("Signal:\nB", markdown)

    def test_symbol_and_composite_signal_aliases_normalize_at_report_boundary(self):
        summaries = pd.DataFrame(
            {
                "Symbol": ["NVDA"],
                "Rank": [1],
                "CompositeScore": [0.84],
                "CompositeSignal": ["B"],
                "ResearchTone": ["NEUTRAL"],
                "ResearchSummary": ["Mixed signals require further review."],
                "AIResearchSummary": ["Further review required."],
                "ReportDate": ["2026-08-08"],
            }
        )
        markdown = research_report_composer.compose_research_report(summaries)
        self.assertIn("### Rank 1 - NVDA", markdown)
        self.assertIn("Signal:\nB", markdown)


if __name__ == "__main__":
    unittest.main()
