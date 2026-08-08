import tempfile
import unittest
from pathlib import Path

import pandas as pd

import ai_research_summary_builder as subject


def explanation_data():
    return pd.DataFrame(
        {
            "Ticker": ["A", "B", "C"],
            "Rank": [3, 1, 2],
            "CompositeScore": [0.7, 0.9, 0.8],
            "TrendSignal": ["BULLISH", "BEARISH", "MIXED"],
            "MomentumSignal": ["STRONG", "NORMAL", "NORMAL"],
            "VolatilitySignal": ["LOW", "HIGH", "LOW"],
            "Signal": ["A", "D", "B"],
            "ResearchTone": ["POSITIVE", "CAUTION", "NEUTRAL"],
            "ResearchSummary": ["Existing A", "Existing B", "Existing C"],
            "ReportDate": ["2026-08-08"] * 3,
        }
    )


class AIResearchSummaryBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_positive_template(self):
        result = subject.build_ai_research_summaries(explanation_data().iloc[[0]])
        self.assertEqual(result.at[0, "AIResearchSummary"], subject.POSITIVE_SUMMARY)

    def test_caution_template(self):
        result = subject.build_ai_research_summaries(explanation_data().iloc[[1]])
        self.assertEqual(result.at[0, "AIResearchSummary"], subject.CAUTION_SUMMARY)

    def test_neutral_and_other_tone_template(self):
        neutral = subject.build_ai_research_summaries(explanation_data().iloc[[2]])
        self.assertEqual(neutral.at[0, "AIResearchSummary"], subject.NEUTRAL_SUMMARY)
        data = explanation_data().iloc[[2]].copy()
        data.loc[:, "ResearchTone"] = "UNKNOWN"
        other = subject.build_ai_research_summaries(data)
        self.assertEqual(other.at[0, "AIResearchSummary"], subject.NEUTRAL_SUMMARY)

    def test_output_fields_and_input_sequence(self):
        result = subject.build_ai_research_summaries(explanation_data())
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(result["Ticker"].tolist(), ["A", "B", "C"])
        self.assertEqual(result["Rank"].tolist(), [3.0, 1.0, 2.0])
        self.assertEqual(result["CompositeScore"].tolist(), [0.7, 0.9, 0.8])

    def test_existing_summary_and_date_are_preserved(self):
        result = subject.build_ai_research_summaries(explanation_data())
        self.assertEqual(
            result["ResearchSummary"].tolist(),
            ["Existing A", "Existing B", "Existing C"],
        )
        self.assertEqual(result["ReportDate"].tolist(), ["2026-08-08"] * 3)

    def test_bad_record_is_isolated(self):
        data = explanation_data()
        data["CompositeScore"] = data["CompositeScore"].astype(object)
        data.loc[1, "CompositeScore"] = "bad"
        result = subject.build_ai_research_summaries(data)
        self.assertEqual(result["Ticker"].tolist(), ["A", "C"])

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MomentumSignal"):
            subject.build_ai_research_summaries(
                explanation_data().drop(columns=["MomentumSignal"])
            )

    def test_empty_input_writes_legal_empty_csv(self):
        input_path = self.root / "empty.csv"
        input_path.write_text("", encoding="utf-8")
        output_path = self.root / "summary.csv"
        result = subject.run_ai_research_summary_builder(input_path, output_path)
        self.assertTrue(result["summaries"].empty)
        self.assertEqual(tuple(pd.read_csv(output_path).columns), subject.OUTPUT_COLUMNS)

    def test_missing_file_writes_legal_empty_csv(self):
        output_path = self.root / "summary.csv"
        result = subject.run_ai_research_summary_builder(
            self.root / "missing.csv", output_path
        )
        self.assertTrue(result["summaries"].empty)
        self.assertTrue(output_path.is_file())

    def test_source_data_is_not_modified(self):
        data = explanation_data()
        original = data.copy(deep=True)
        subject.build_ai_research_summaries(data)
        pd.testing.assert_frame_equal(data, original)

    def test_no_forbidden_dependencies_or_external_api(self):
        source = Path(subject.__file__).read_text(encoding="utf-8").lower()
        for term in ("portfolio", "watchlist", "broker", "requests", "openai"):
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
