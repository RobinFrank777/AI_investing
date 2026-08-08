import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from daily_report.generator import DISCLAIMER, generate_daily_report


class DailyReportGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = {
            name: self.root / f"{name}.csv"
            for name in ("candidate", "summary", "validation", "risk", "alert", "pipeline")
        }
        candidates = pd.DataFrame(
            {
                "Ticker": [f"T{i}" for i in range(1, 13)],
                "Rank": list(range(1, 13)),
                "CompositeScore": [f"score-{i}" for i in range(1, 13)],
                "Signal": [f"signal-{i}" for i in range(1, 13)],
                "CandidateStatus": ["READY"] * 12,
                "ReportDate": ["2026-08-08"] * 12,
            }
        )
        summaries = pd.DataFrame(
            {
                "Ticker": ["T2", "T1"],
                "ResearchTone": ["CAUTION", "POSITIVE"],
                "ResearchSummary": ["summary two", "summary one"],
                "AIResearchSummary": ["AI two", "AI one"],
            }
        )
        validation = pd.DataFrame(
            {"CheckItem": ["MissingMetricValueCount", "OverallStatus"], "Value": [2, "PARTIAL"], "Status": ["PARTIAL", "PARTIAL"]}
        )
        risk = pd.DataFrame({"Ticker": ["T1"], "Status": ["PASS"], "ObservationCount": [300]})
        alerts = pd.DataFrame(
            {"Symbol": ["T2"], "AlertType": ["RESEARCH_WARNING"], "AlertLevel": ["WATCH"], "Description": ["Manual review required."]}
        )
        pipeline = pd.DataFrame({"StepName": ["One"], "Status": ["PASS"], "Message": ["completed"], "RunDate": ["2026-08-08"]})
        for frame, key in ((candidates, "candidate"), (summaries, "summary"), (validation, "validation"), (risk, "risk"), (alerts, "alert"), (pipeline, "pipeline")):
            frame.to_csv(self.paths[key], index=False)

    def tearDown(self):
        self.temp.cleanup()

    def generate(self, **overrides):
        kwargs = {f"{name}_path": path for name, path in self.paths.items()}
        kwargs["output_path"] = self.root / "report.md"
        kwargs["generated_at"] = datetime(2026, 8, 8, 10, 30, tzinfo=timezone.utc)
        kwargs.update(overrides)
        return generate_daily_report(**kwargs)

    def test_normal_artifacts_generate_markdown(self):
        result = self.generate()
        self.assertTrue(Path(result["report_path"]).is_file())
        self.assertIn("# AI_investing Daily Investment Report", result["markdown"])

    def test_top_candidates_are_limited_to_ten(self):
        markdown = self.generate()["markdown"]
        self.assertIn("| 10 | T10 |", markdown)
        self.assertNotIn("| 11 | T11 |", markdown)

    def test_rank_order_is_preserved(self):
        frame = pd.read_csv(self.paths["candidate"])
        frame = frame.iloc[[2, 0, 1]]
        frame.to_csv(self.paths["candidate"], index=False)
        markdown = self.generate()["markdown"]
        self.assertLess(markdown.index("| 3 | T3 |"), markdown.index("| 1 | T1 |"))

    def test_symbol_alias_is_supported(self):
        frame = pd.read_csv(self.paths["candidate"]).rename(columns={"Ticker": "Symbol"})
        frame.to_csv(self.paths["candidate"], index=False)
        self.assertIn("| 1 | T1 |", self.generate()["markdown"])

    def test_summary_aligns_by_ticker(self):
        markdown = self.generate()["markdown"]
        first = markdown.index("### Rank 1 — T1")
        second = markdown.index("### Rank 2 — T2")
        self.assertIn("AI one", markdown[first:second])
        self.assertIn("AI two", markdown[second:])

    def test_partial_validation_is_prominent(self):
        markdown = self.generate()["markdown"]
        self.assertIn("**DATA QUALITY WARNING: Validation Status is PARTIAL.**", markdown)

    def test_risk_alert_is_displayed(self):
        self.assertIn("Manual review required.", self.generate()["markdown"])

    def test_no_risk_alerts_message(self):
        pd.DataFrame(columns=["Symbol", "AlertType", "AlertLevel", "Description"]).to_csv(self.paths["alert"], index=False)
        self.assertIn("No active risk alerts.", self.generate()["markdown"])

    def test_missing_artifact_does_not_crash(self):
        missing = self.root / "missing.csv"
        markdown = self.generate(summary_path=missing)["markdown"]
        self.assertIn("AI Research Summary: Data unavailable.", markdown)

    def test_empty_csv_does_not_crash(self):
        self.paths["risk"].write_text("", encoding="utf-8")
        self.assertIn("Risk: artifact is empty.", self.generate()["markdown"])

    def test_missing_columns_show_schema_warning(self):
        pd.DataFrame({"Other": [1]}).to_csv(self.paths["candidate"], index=False)
        markdown = self.generate()["markdown"]
        self.assertIn("Candidate schema warning", markdown)
        self.assertIn("Data unavailable.", markdown)

    def test_existing_values_are_not_recalculated(self):
        markdown = self.generate()["markdown"]
        self.assertIn("score-1", markdown)
        self.assertIn("signal-1", markdown)

    def test_disclaimer_is_included(self):
        self.assertIn(DISCLAIMER, self.generate()["markdown"])


if __name__ == "__main__":
    unittest.main()
