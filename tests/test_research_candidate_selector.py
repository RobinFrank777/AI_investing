import tempfile
import unittest
from pathlib import Path

import pandas as pd

import research_candidate_selector as subject


def research_data():
    return pd.DataFrame(
        {
            "Ticker": ["A", "B", "C"],
            "Rank": [2, 1, 3],
            "CompositeScore": [0.8, 0.9, 0.7],
            "TrendSignal": ["STRONG", "STRONG", "NORMAL"],
            "MomentumSignal": ["POSITIVE", "POSITIVE", "NEUTRAL"],
            "VolatilitySignal": ["LOW", "LOW", "NORMAL"],
            "CompositeSignal": ["B", "A", "B"],
            "RiskStatus": ["PASS", "PASS", "PARTIAL"],
            "ResearchStatus": ["PASS", "PASS", "PASS"],
        }
    )


class ResearchCandidateSelectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_pass_data_becomes_ready_candidate(self):
        result = subject.select_research_candidates(research_data().iloc[[0]])
        self.assertEqual(result.at[0, "Ticker"], "A")
        self.assertEqual(result.at[0, "CandidateStatus"], "READY")
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_failed_risk_is_excluded(self):
        data = research_data().iloc[[0]].copy()
        data.loc[:, "RiskStatus"] = "FAILED"
        result = subject.select_research_candidates(data)
        self.assertTrue(result.empty)

    def test_partial_risk_is_retained_for_review(self):
        result = subject.select_research_candidates(research_data().iloc[[2]])
        self.assertEqual(result.at[0, "CandidateStatus"], "REVIEW")

    def test_missing_field_is_rejected(self):
        data = research_data().drop(columns=["CompositeSignal"])
        with self.assertRaisesRegex(ValueError, "CompositeSignal"):
            subject.select_research_candidates(data)

    def test_empty_input_writes_legal_empty_csv(self):
        input_path = self.root / "empty.csv"
        input_path.write_text("", encoding="utf-8")
        output_path = self.root / "candidates.csv"
        result = subject.run_candidate_selector(input_path, output_path)
        self.assertTrue(result["candidates"].empty)
        saved = pd.read_csv(output_path)
        self.assertEqual(tuple(saved.columns), subject.OUTPUT_COLUMNS)

    def test_missing_input_writes_legal_empty_csv(self):
        output_path = self.root / "candidates.csv"
        result = subject.run_candidate_selector(
            self.root / "missing.csv", output_path
        )
        self.assertTrue(result["candidates"].empty)
        self.assertTrue(output_path.is_file())

    def test_sort_is_stable_and_uses_existing_rank(self):
        data = research_data()
        data.loc[:, "Rank"] = [2, 1, 2]
        result = subject.select_research_candidates(data)
        self.assertEqual(result["Ticker"].tolist(), ["B", "A", "C"])
        self.assertEqual(result["Rank"].tolist(), [1.0, 2.0, 2.0])

    def test_bad_rows_are_isolated(self):
        data = research_data()
        data.loc[0, "Ticker"] = ""
        data["Rank"] = data["Rank"].astype(object)
        data.loc[1, "Rank"] = "bad"
        result = subject.select_research_candidates(data)
        self.assertEqual(result["Ticker"].tolist(), ["C"])
        self.assertEqual(result.at[0, "CandidateStatus"], "REVIEW")

    def test_research_non_pass_is_excluded(self):
        data = research_data().iloc[[0]].copy()
        data.loc[:, "ResearchStatus"] = "PARTIAL"
        self.assertTrue(subject.select_research_candidates(data).empty)

    def test_source_dataframe_is_not_modified(self):
        data = research_data()
        original = data.copy(deep=True)
        subject.select_research_candidates(data)
        pd.testing.assert_frame_equal(data, original)

    def test_no_forbidden_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8").lower()
        forbidden = ("portfolio", "watchlist", "broker", "execution module")
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
