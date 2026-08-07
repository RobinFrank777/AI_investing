import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

import candidate_report_builder as subject


def candidate_data():
    return pd.DataFrame(
        {
            "Ticker": ["A", "B", "C"],
            "Rank": [3, 1, 2],
            "CompositeScore": [0.7, 0.9, 0.8],
            "TrendSignal": ["NORMAL", "STRONG", "STRONG"],
            "MomentumSignal": ["NEUTRAL", "POSITIVE", "POSITIVE"],
            "VolatilitySignal": ["NORMAL", "LOW", "LOW"],
            "CompositeSignal": ["B", "A", "B"],
            "RiskStatus": ["PASS", "PARTIAL", "FAILED"],
            "CandidateStatus": ["READY", "REVIEW", "EXCLUDED"],
        }
    )


class CandidateReportBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_ready_maps_to_high(self):
        result = subject.build_candidate_report(candidate_data().iloc[[0]])
        self.assertEqual(result.at[0, "ResearchPriority"], "HIGH")

    def test_review_maps_to_medium(self):
        result = subject.build_candidate_report(candidate_data().iloc[[1]])
        self.assertEqual(result.at[0, "ResearchPriority"], "MEDIUM")

    def test_other_status_maps_to_low(self):
        result = subject.build_candidate_report(candidate_data().iloc[[2]])
        self.assertEqual(result.at[0, "ResearchPriority"], "LOW")

    def test_input_report_date_has_priority(self):
        data = candidate_data().iloc[[0]].copy()
        data["ReportDate"] = ["2026-07-31"]
        result = subject.build_candidate_report(data, generation_date="2020-01-01")
        self.assertEqual(result.at[0, "ReportDate"], "2026-07-31")

    def test_default_date_uses_generation_date(self):
        result = subject.build_candidate_report(candidate_data().iloc[[0]])
        self.assertEqual(result.at[0, "ReportDate"], date.today().isoformat())

    def test_input_sequence_is_preserved(self):
        result = subject.build_candidate_report(candidate_data())
        self.assertEqual(result["Ticker"].tolist(), ["A", "B", "C"])
        self.assertEqual(result["Rank"].tolist(), [3.0, 1.0, 2.0])
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_empty_input_writes_full_empty_contract(self):
        input_path = self.root / "empty.csv"
        input_path.write_text("", encoding="utf-8")
        output_path = self.root / "report.csv"
        result = subject.run_candidate_report(input_path, output_path)
        self.assertTrue(result["report"].empty)
        self.assertEqual(tuple(pd.read_csv(output_path).columns), subject.OUTPUT_COLUMNS)

    def test_missing_file_writes_full_empty_contract(self):
        output_path = self.root / "report.csv"
        result = subject.run_candidate_report(self.root / "missing.csv", output_path)
        self.assertTrue(result["report"].empty)
        self.assertTrue(output_path.is_file())

    def test_bad_record_is_skipped_without_affecting_others(self):
        data = candidate_data()
        data["Rank"] = data["Rank"].astype(object)
        data.loc[1, "Rank"] = "bad"
        result = subject.build_candidate_report(data)
        self.assertEqual(result["Ticker"].tolist(), ["A", "C"])

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "TrendSignal"):
            subject.build_candidate_report(
                candidate_data().drop(columns=["TrendSignal"])
            )

    def test_source_data_is_not_modified(self):
        data = candidate_data()
        original = data.copy(deep=True)
        subject.build_candidate_report(data)
        pd.testing.assert_frame_equal(data, original)

    def test_no_forbidden_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8").lower()
        for term in ("portfolio", "broker", "trading pipeline", "ai commentary"):
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
