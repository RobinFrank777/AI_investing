import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import research_pipeline_logger as subject


def pipeline_status(statuses):
    return pd.DataFrame(
        {
            "StepName": [f"Step{number}" for number in range(1, len(statuses) + 1)],
            "Status": statuses,
            "Message": [
                "completed" if status == "PASS" else f"{status.lower()} message"
                for status in statuses
            ],
            "RunDate": ["2026-08-08"] * len(statuses),
        }
    )


class ResearchPipelineLoggerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log_dir = Path(self.temp.name) / "logs"

    def test_normal_log_is_saved_with_fixed_structure(self):
        path = subject.save_pipeline_log(
            pipeline_status(["PASS", "PASS"]), log_dir=self.log_dir
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["run_date"], "2026-08-08")
        self.assertEqual(payload["pipeline_status"], "PASS")
        self.assertEqual(
            payload["summary"], {"PASS": 2, "FAILED": 0, "SKIPPED": 0}
        )
        self.assertEqual(
            tuple(payload), ("run_date", "pipeline_status", "steps", "summary")
        )

    def test_failed_status_and_error_are_saved(self):
        payload = subject.build_pipeline_log(
            pipeline_status(["PASS", "FAILED", "SKIPPED"])
        )
        self.assertEqual(payload["pipeline_status"], "PARTIAL")
        self.assertEqual(payload["steps"][1]["status"], "FAILED")
        self.assertEqual(payload["steps"][1]["error"], "failed message")
        self.assertEqual(payload["summary"]["FAILED"], 1)

    def test_skipped_status_and_message_are_saved(self):
        payload = subject.build_pipeline_log(
            pipeline_status(["PASS", "SKIPPED"])
        )
        self.assertEqual(payload["steps"][1]["status"], "SKIPPED")
        self.assertEqual(payload["steps"][1]["error"], "skipped message")
        self.assertEqual(payload["summary"]["SKIPPED"], 1)

    def test_empty_pipeline_has_legal_log(self):
        payload = subject.build_pipeline_log(None, run_date="2026-08-08")
        self.assertEqual(payload["pipeline_status"], "EMPTY")
        self.assertEqual(payload["steps"], [])
        self.assertEqual(
            payload["summary"], {"PASS": 0, "FAILED": 0, "SKIPPED": 0}
        )

    def test_log_path_uses_compact_run_date_and_creates_directory(self):
        expected = self.log_dir / "daily_research_pipeline_20260808.json"
        self.assertEqual(
            subject.pipeline_log_path("2026-08-08", self.log_dir), expected
        )
        path = subject.save_pipeline_log(
            pipeline_status(["FAILED"]), log_dir=self.log_dir
        )
        self.assertEqual(path, expected)
        self.assertTrue(path.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["pipeline_status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
