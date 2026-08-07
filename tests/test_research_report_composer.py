import tempfile
import unittest
from pathlib import Path

import pandas as pd

import research_report_composer as subject


def summary_data():
    return pd.DataFrame(
        {
            "Rank": [2, 1],
            "Symbol": ["AMD", "NVDA"],
            "CompositeScore": [81.5, 92.5],
            "Signal": ["NORMAL", "STRONG"],
            "ResearchTone": ["NEUTRAL", "POSITIVE"],
            "ResearchSummary": ["Mixed profile.", "Strong profile."],
            "AIResearchSummary": ["Review further.", "Fundamental review."],
            "ReportDate": ["2026-08-08", "2026-08-08"],
        }
    )


class ResearchReportComposerTests(unittest.TestCase):
    def test_normal_report_generation_preserves_sequence_and_values(self):
        report = subject.compose_research_report(summary_data())
        self.assertLess(
            report.index("### Rank 2 - AMD"), report.index("### Rank 1 - NVDA")
        )
        self.assertIn("Composite Score:\n81.5", report)
        self.assertIn("Signal:\nSTRONG", report)
        self.assertIn("Research Tone:\nPOSITIVE", report)
        self.assertIn("Research Summary:\n\nStrong profile.", report)
        self.assertIn("AI Research Summary:\n\nFundamental review.", report)

    def test_report_structure_and_date(self):
        report = subject.compose_research_report(summary_data())
        self.assertTrue(report.startswith("# AI_investing Research Report\n"))
        self.assertIn("Report Date:\n2026-08-08", report)
        self.assertIn("## Research Candidates", report)
        self.assertIn("\n---\n", report)

    def test_missing_file_generates_legal_empty_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "report.md"
            result = subject.generate_research_report(root / "missing.csv", output)
            self.assertEqual(result["markdown"], subject.EMPTY_REPORT)
            self.assertEqual(output.read_text(encoding="utf-8"), subject.EMPTY_REPORT)

    def test_empty_file_generates_legal_empty_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "empty.csv"
            source.write_text("", encoding="utf-8")
            output = root / "report.md"
            result = subject.generate_research_report(source, output)
            self.assertEqual(result["markdown"], subject.EMPTY_REPORT)
            self.assertTrue(output.is_file())

    def test_header_only_csv_generates_legal_empty_report(self):
        empty = pd.DataFrame(columns=subject.REQUIRED_COLUMNS)
        self.assertEqual(subject.compose_research_report(empty), subject.EMPTY_REPORT)

    def test_missing_core_field_has_clear_error(self):
        for missing in ("Rank", "Symbol", "CompositeScore", "Signal"):
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(ValueError, missing):
                    subject.compose_research_report(
                        summary_data().drop(columns=[missing])
                    )

    def test_missing_research_text_field_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "AIResearchSummary"):
            subject.compose_research_report(
                summary_data().drop(columns=["AIResearchSummary"])
            )

    def test_bad_record_is_skipped_without_affecting_other_rows(self):
        data = summary_data()
        data["Rank"] = data["Rank"].astype(object)
        data.loc[0, "Rank"] = None
        report = subject.compose_research_report(data)
        self.assertNotIn("AMD", report)
        self.assertIn("### Rank 1 - NVDA", report)

    def test_source_dataframe_is_not_modified(self):
        data = summary_data()
        original = data.copy(deep=True)
        subject.compose_research_report(data)
        pd.testing.assert_frame_equal(data, original)

    def test_output_file_is_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "summary.csv"
            output = root / "nested" / "report.md"
            summary_data().to_csv(source, index=False)
            result = subject.generate_research_report(source, output)
            self.assertEqual(result["report_path"], str(output))
            self.assertTrue(output.is_file())

    def test_no_calculation_module_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8").lower()
        for term in ("factor_normalization", "factor_ranking", "signal_engine"):
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
