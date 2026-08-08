import unittest
from unittest import mock

import pandas as pd

import daily_research_scheduler as subject


def pipeline_result(statuses):
    return {
        "status": pd.DataFrame(
            {
                "StepName": [f"Step{number}" for number in range(len(statuses))],
                "Status": statuses,
                "Message": ["completed"] * len(statuses),
                "RunDate": ["2026-08-08"] * len(statuses),
            }
        ),
        "output_path": "results/daily_research_pipeline_status.csv",
    }


class DailyResearchSchedulerTests(unittest.TestCase):
    def setUp(self):
        pipeline_patch = mock.patch.object(
            subject.daily_research_pipeline, "run_daily_research_pipeline"
        )
        log_patch = mock.patch.object(
            subject.research_pipeline_logger,
            "pipeline_log_path",
            return_value="logs/daily_research_pipeline_20260808.json",
        )
        self.pipeline = pipeline_patch.start()
        self.log_path = log_patch.start()
        self.addCleanup(pipeline_patch.stop)
        self.addCleanup(log_patch.stop)

    def test_normal_execution_returns_pass(self):
        self.pipeline.return_value = pipeline_result(["PASS"] * 13)
        result = subject.run_scheduled_research("2026-08-08")
        self.assertEqual(result["PipelineStatus"], "PASS")
        self.assertEqual(
            result["Summary"], {"PASS": 13, "FAILED": 0, "SKIPPED": 0}
        )
        self.assertEqual(
            result["LogPath"], "logs/daily_research_pipeline_20260808.json"
        )

    def test_explicit_date_is_forwarded_and_returned(self):
        self.pipeline.return_value = pipeline_result(["PASS"] * 13)
        result = subject.run_scheduled_research("2026-08-08")
        self.assertEqual(result["RunDate"], "2026-08-08")
        self.pipeline.assert_called_once_with(run_date="2026-08-08")
        self.log_path.assert_called_once_with("2026-08-08")

    def test_failed_pipeline_result_returns_failed(self):
        self.pipeline.return_value = pipeline_result(
            ["PASS"] * 4 + ["FAILED"] + ["SKIPPED"] * 8
        )
        result = subject.run_scheduled_research("2026-08-08")
        self.assertEqual(result["PipelineStatus"], "FAILED")
        self.assertEqual(
            result["Summary"], {"PASS": 4, "FAILED": 1, "SKIPPED": 8}
        )

    def test_pipeline_exception_returns_legal_failed_result(self):
        self.pipeline.side_effect = RuntimeError("unexpected failure")
        result = subject.run_scheduled_research("2026-08-08")
        self.assertEqual(
            result,
            {
                "RunDate": "2026-08-08",
                "PipelineStatus": "FAILED",
                "LogPath": "logs/daily_research_pipeline_20260808.json",
                "Summary": {"PASS": 0, "FAILED": 0, "SKIPPED": 0},
            },
        )

    def test_logger_is_mocked_and_no_real_log_is_written(self):
        self.pipeline.return_value = pipeline_result(["PASS"] * 13)
        result = subject.run_scheduled_research("2026-08-08")
        self.assertEqual(
            result["LogPath"], "logs/daily_research_pipeline_20260808.json"
        )
        self.log_path.assert_called_once_with("2026-08-08")
        source = subject.__file__
        self.assertTrue(source.endswith("daily_research_scheduler.py"))


if __name__ == "__main__":
    unittest.main()
