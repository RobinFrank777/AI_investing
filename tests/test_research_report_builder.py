import tempfile
import unittest
from pathlib import Path

import pandas as pd

import research_report_builder as subject


def ranking_frame(size=12):
    return pd.DataFrame(
        {
            "Rank": list(range(size, 0, -1)),
            "Ticker": [f"T{index:02d}" for index in range(size)],
            "TrendValue": [index / 100 for index in range(size)],
            "MomentumValue": [index / 90 for index in range(size)],
            "Volatility20D": [index / 80 for index in range(size)],
            "LowVolScore": [index / max(size, 1) for index in range(size)],
            "CompositeScore": [index / 70 for index in range(size)],
        }
    )


class ResearchReportBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_ranking(self, frame=None):
        path = self.root / "universe150_factor_ranking.csv"
        (ranking_frame() if frame is None else frame).to_csv(path, index=False)
        return path

    def test_normal_ranking_file_is_loaded(self):
        expected = ranking_frame()
        loaded = subject.load_factor_ranking(self.write_ranking(expected))
        pd.testing.assert_frame_equal(loaded, expected)

    def test_default_top_ten_is_sorted_by_rank(self):
        report = subject.build_research_report(ranking_frame())
        self.assertEqual(len(report), 10)
        self.assertEqual(report["Rank"].tolist(), list(range(1, 11)))
        self.assertEqual(report.columns.tolist(), list(subject.REPORT_COLUMNS))

    def test_custom_top_n_is_respected(self):
        report = subject.build_research_report(ranking_frame(), top_n=3)
        self.assertEqual(report["Rank"].tolist(), [1, 2, 3])
        with self.assertRaisesRegex(ValueError, "positive integer"):
            subject.build_research_report(ranking_frame(), top_n=0)

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "LowVolScore"):
            subject.build_research_report(
                ranking_frame().drop(columns=["LowVolScore"])
            )

    def test_empty_data_returns_empty_fixed_schema(self):
        empty = pd.DataFrame(columns=subject.REPORT_COLUMNS)
        report = subject.build_research_report(empty)
        self.assertTrue(report.empty)
        self.assertEqual(report.columns.tolist(), list(subject.REPORT_COLUMNS))

    def test_missing_file_has_clear_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "factor ranking file not found"):
            subject.load_factor_ranking(self.root / "missing.csv")

    def test_bad_records_do_not_affect_valid_records(self):
        ranking = ranking_frame(4)
        ranking["Rank"] = ranking["Rank"].astype(object)
        ranking.loc[0, "Rank"] = "bad"
        ranking.loc[1, "CompositeScore"] = None
        ranking.loc[2, "Ticker"] = None
        report = subject.build_research_report(ranking)
        self.assertEqual(len(report), 1)
        self.assertEqual(report.iloc[0]["Ticker"], "T03")

    def test_run_saves_expected_report(self):
        output = self.root / "results" / "universe150_research_report.csv"
        result = subject.run_research_report(
            self.write_ranking(), output, top_n=2
        )
        self.assertEqual(result["output_path"], str(output))
        self.assertEqual(result["summary"], {"rows": 2, "top_n": 2})
        saved = pd.read_csv(output)
        self.assertEqual(saved.columns.tolist(), list(subject.REPORT_COLUMNS))
        self.assertEqual(saved["Rank"].tolist(), [1, 2])

    def test_no_trading_or_production_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "import watchlist",
            "import portfolio",
            "import broker",
            "import order",
            "import run_all",
        )
        for reference in forbidden_references:
            with self.subTest(reference=reference):
                self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
