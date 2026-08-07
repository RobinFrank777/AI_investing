import tempfile
import unittest
from datetime import date as real_date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import research_report_renderer as subject


def report_frame():
    return pd.DataFrame(
        {
            "Rank": [2, 1],
            "Ticker": ["AVGO", "NVDA"],
            "TrendValue": [0.80, 0.95],
            "MomentumValue": [0.70, 0.92],
            "Volatility20D": [0.40, 0.35],
            "LowVolScore": [0.75, 0.85],
            "CompositeScore": [0.81, 0.91],
        }
    )


class ResearchReportRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_report(self, frame=None):
        path = self.root / "universe150_research_report.csv"
        (report_frame() if frame is None else frame).to_csv(path, index=False)
        return path

    def test_normal_markdown_generation(self):
        output = self.root / "reports" / "report.md"
        result = subject.generate_report(self.write_report(), output)
        self.assertEqual(result, output)
        markdown = output.read_text(encoding="utf-8")
        self.assertIn("# AI_investing Universe150 Research Report", markdown)
        self.assertIn("- Universe: Universe150", markdown)
        self.assertIn("- Candidates Count: 2", markdown)

    def test_table_fields_are_exact_and_input_order_is_preserved(self):
        markdown = subject.render_report_markdown(report_frame())
        expected_header = "| " + " | ".join(subject.REPORT_COLUMNS) + " |"
        self.assertIn(expected_header, markdown)
        self.assertLess(markdown.index("| 2 | AVGO |"), markdown.index("| 1 | NVDA |"))

    def test_input_report_date_is_used_when_available(self):
        report = report_frame()
        report["ReportDate"] = ["2026-08-07", "2026-08-07"]
        markdown = subject.render_report_markdown(report)
        self.assertIn("- Report Date: 2026-08-07", markdown)

    def test_generation_date_is_used_when_input_has_no_date(self):
        with patch.object(subject, "date") as mocked_date:
            mocked_date.today.return_value = real_date(2026, 8, 8)
            markdown = subject.render_report_markdown(report_frame())
        self.assertIn("- Report Date: 2026-08-08", markdown)

    def test_empty_data_generates_valid_markdown(self):
        empty = pd.DataFrame(columns=subject.REPORT_COLUMNS)
        markdown = subject.render_report_markdown(empty)
        self.assertIn("- Candidates Count: 0", markdown)
        self.assertIn("No valid research candidates.", markdown)

    def test_invalid_record_is_omitted_without_reordering_valid_rows(self):
        report = report_frame()
        report.loc[0, "CompositeScore"] = None
        markdown = subject.render_report_markdown(report)
        self.assertNotIn("AVGO", markdown)
        self.assertIn("NVDA", markdown)
        self.assertIn("- Candidates Count: 1", markdown)

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "LowVolScore"):
            subject.render_report_markdown(
                report_frame().drop(columns=["LowVolScore"])
            )

    def test_missing_input_file_has_clear_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "report file not found"):
            subject.generate_report(self.root / "missing.csv", self.root / "x.md")

    def test_no_forbidden_dependencies_or_commentary_generation(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "import portfolio",
            "import watchlist",
            "import broker",
            "import order",
            "import run_all",
            "generate_signal",
            "buy_recommendation",
            "sell_recommendation",
            "openai",
        )
        for reference in forbidden_references:
            with self.subTest(reference=reference):
                self.assertNotIn(reference, source.lower())


if __name__ == "__main__":
    unittest.main()
