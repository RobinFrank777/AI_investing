import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

import daily_research_snapshot as subject


def candidate_report():
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
            "ResearchPriority": ["HIGH", "MEDIUM", "LOW"],
        }
    )


class DailyResearchSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_normal_snapshot_generation(self):
        result = subject.build_daily_snapshot(
            candidate_report(), generation_date="2026-08-01"
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result["Ticker"].tolist(), ["A", "B", "C"])

    def test_output_field_sequence(self):
        result = subject.build_daily_snapshot(candidate_report())
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_input_report_date_has_priority(self):
        data = candidate_report().iloc[[0]].copy()
        data["ReportDate"] = ["2026-07-31"]
        result = subject.build_daily_snapshot(data, generation_date="2020-01-01")
        self.assertEqual(result.at[0, "ReportDate"], "2026-07-31")

    def test_default_date_is_current_date(self):
        result = subject.build_daily_snapshot(candidate_report().iloc[[0]])
        self.assertEqual(result.at[0, "ReportDate"], date.today().isoformat())

    def test_ready_and_review_are_active(self):
        result = subject.build_daily_snapshot(candidate_report().iloc[:2])
        self.assertEqual(result["SnapshotStatus"].tolist(), ["ACTIVE", "ACTIVE"])

    def test_other_candidate_state_is_invalid(self):
        result = subject.build_daily_snapshot(candidate_report().iloc[[2]])
        self.assertEqual(result.at[0, "SnapshotStatus"], "INVALID")

    def test_input_sequence_and_values_are_preserved(self):
        result = subject.build_daily_snapshot(candidate_report())
        self.assertEqual(result["Rank"].tolist(), [3.0, 1.0, 2.0])
        self.assertEqual(result["CompositeScore"].tolist(), [0.7, 0.9, 0.8])
        self.assertEqual(result["CompositeSignal"].tolist(), ["B", "A", "B"])

    def test_empty_input_writes_legal_empty_snapshot(self):
        input_path = self.root / "empty.csv"
        input_path.write_text("", encoding="utf-8")
        output_path = self.root / "snapshot.csv"
        result = subject.run_daily_snapshot(input_path, output_path)
        self.assertTrue(result["snapshot"].empty)
        self.assertEqual(tuple(pd.read_csv(output_path).columns), subject.OUTPUT_COLUMNS)

    def test_missing_input_writes_legal_empty_snapshot(self):
        output_path = self.root / "snapshot.csv"
        result = subject.run_daily_snapshot(self.root / "missing.csv", output_path)
        self.assertTrue(result["snapshot"].empty)
        self.assertTrue(output_path.is_file())

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ResearchPriority"):
            subject.build_daily_snapshot(
                candidate_report().drop(columns=["ResearchPriority"])
            )

    def test_bad_record_is_isolated(self):
        data = candidate_report()
        data["CompositeScore"] = data["CompositeScore"].astype(object)
        data.loc[1, "CompositeScore"] = "bad"
        result = subject.build_daily_snapshot(data)
        self.assertEqual(result["Ticker"].tolist(), ["A", "C"])

    def test_source_data_is_not_modified(self):
        data = candidate_report()
        original = data.copy(deep=True)
        subject.build_daily_snapshot(data)
        pd.testing.assert_frame_equal(data, original)

    def test_no_forbidden_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8").lower()
        for term in ("portfolio", "watchlist", "broker", "trading pipeline"):
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
