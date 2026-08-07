import tempfile
import unittest
from pathlib import Path

import pandas as pd

import research_explanation_engine as subject


def snapshot_data():
    return pd.DataFrame(
        {
            "Ticker": ["A", "B", "C"],
            "Rank": [3, 1, 2],
            "CompositeScore": [0.7, 0.9, 0.8],
            "TrendSignal": ["BULLISH", "BEARISH", "MIXED"],
            "MomentumSignal": ["STRONG", "NORMAL", "NORMAL"],
            "VolatilitySignal": ["LOW", "HIGH", "LOW"],
            "SnapshotStatus": ["ACTIVE", "ACTIVE", "ACTIVE"],
            "ReportDate": ["2026-08-08"] * 3,
        }
    )


class ResearchExplanationEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_positive_tone_and_summary(self):
        result = subject.build_research_explanations(snapshot_data().iloc[[0]])
        self.assertEqual(result.at[0, "ResearchTone"], "POSITIVE")
        self.assertEqual(
            result.at[0, "ResearchSummary"],
            "Strong trend and momentum with controlled volatility.",
        )

    def test_caution_tone_for_bearish_or_weak(self):
        bearish = subject.build_research_explanations(snapshot_data().iloc[[1]])
        self.assertEqual(bearish.at[0, "ResearchTone"], "CAUTION")
        data = snapshot_data().iloc[[2]].copy()
        data.loc[:, "MomentumSignal"] = "WEAK"
        weak = subject.build_research_explanations(data)
        self.assertEqual(weak.at[0, "ResearchTone"], "CAUTION")

    def test_neutral_tone_and_summary(self):
        result = subject.build_research_explanations(snapshot_data().iloc[[2]])
        self.assertEqual(result.at[0, "ResearchTone"], "NEUTRAL")
        self.assertEqual(
            result.at[0, "ResearchSummary"],
            "Mixed signals require further review.",
        )

    def test_output_fields_and_input_sequence(self):
        result = subject.build_research_explanations(snapshot_data())
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(result["Ticker"].tolist(), ["A", "B", "C"])
        self.assertEqual(result["Rank"].tolist(), [3.0, 1.0, 2.0])
        self.assertEqual(result["CompositeScore"].tolist(), [0.7, 0.9, 0.8])

    def test_inactive_record_is_skipped(self):
        data = snapshot_data()
        data.loc[1, "SnapshotStatus"] = "INVALID"
        result = subject.build_research_explanations(data)
        self.assertEqual(result["Ticker"].tolist(), ["A", "C"])

    def test_bad_record_is_isolated(self):
        data = snapshot_data()
        data["Rank"] = data["Rank"].astype(object)
        data.loc[1, "Rank"] = "bad"
        result = subject.build_research_explanations(data)
        self.assertEqual(result["Ticker"].tolist(), ["A", "C"])

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ReportDate"):
            subject.build_research_explanations(
                snapshot_data().drop(columns=["ReportDate"])
            )

    def test_empty_input_writes_legal_empty_csv(self):
        input_path = self.root / "empty.csv"
        input_path.write_text("", encoding="utf-8")
        output_path = self.root / "explanations.csv"
        result = subject.run_explanation_engine(input_path, output_path)
        self.assertTrue(result["explanations"].empty)
        self.assertEqual(tuple(pd.read_csv(output_path).columns), subject.OUTPUT_COLUMNS)

    def test_missing_file_writes_legal_empty_csv(self):
        output_path = self.root / "explanations.csv"
        result = subject.run_explanation_engine(self.root / "missing.csv", output_path)
        self.assertTrue(result["explanations"].empty)
        self.assertTrue(output_path.is_file())

    def test_report_date_is_preserved(self):
        result = subject.build_research_explanations(snapshot_data().iloc[[0]])
        self.assertEqual(result.at[0, "ReportDate"], "2026-08-08")

    def test_source_data_is_not_modified(self):
        data = snapshot_data()
        original = data.copy(deep=True)
        subject.build_research_explanations(data)
        pd.testing.assert_frame_equal(data, original)

    def test_no_forbidden_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8").lower()
        for term in ("portfolio", "watchlist", "broker"):
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
