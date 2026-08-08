import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import pandas as pd

import daily_research_cli as subject


def pipeline_result(statuses=None, output_path="results/daily_research_pipeline_status.csv"):
    values = ["PASS"] * 13 if statuses is None else statuses
    return {
        "status": pd.DataFrame(
            {
                "StepName": [f"Step{number}" for number in range(1, 14)],
                "Status": values,
                "Message": ["completed"] * 13,
                "RunDate": ["2026-08-08"] * 13,
            }
        ),
        "output_path": output_path,
    }


class DailyResearchCLITests(unittest.TestCase):
    def test_normal_run_calls_pipeline_and_prints_summary(self):
        with mock.patch.object(
            subject.daily_research_pipeline,
            "run_daily_research_pipeline",
            return_value=pipeline_result(),
        ) as runner:
            output = io.StringIO()
            with redirect_stdout(output):
                code = subject.main([])
        self.assertEqual(code, 0)
        runner.assert_called_once_with()
        rendered = output.getvalue()
        self.assertIn("Daily Research Pipeline Completed", rendered)
        self.assertIn("PASS:\n13", rendered)
        self.assertIn("FAILED:\n0", rendered)
        self.assertIn("SKIPPED:\n0", rendered)
        self.assertIn("results/daily_research_pipeline_status.csv", rendered)

    def test_dry_run_prints_sequence_without_running_pipeline(self):
        with mock.patch.object(
            subject.daily_research_pipeline, "run_daily_research_pipeline"
        ) as runner:
            output = io.StringIO()
            with redirect_stdout(output):
                code = subject.main(["--dry-run"])
        self.assertEqual(code, 0)
        runner.assert_not_called()
        lines = output.getvalue()
        self.assertIn("1. Factor Preparation", lines)
        self.assertIn("13. Report Composer", lines)

    def test_invalid_argument_returns_nonzero(self):
        errors = io.StringIO()
        with redirect_stderr(errors):
            with self.assertRaises(SystemExit) as raised:
                subject.main(["--unknown"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("unrecognized arguments", errors.getvalue())

    def test_pipeline_exception_is_caught_without_traceback(self):
        with mock.patch.object(
            subject.daily_research_pipeline,
            "run_daily_research_pipeline",
            side_effect=RuntimeError("dataset unavailable"),
        ):
            errors = io.StringIO()
            with redirect_stderr(errors):
                code = subject.main([])
        self.assertEqual(code, 1)
        self.assertIn("dataset unavailable", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_failed_pipeline_status_returns_nonzero_and_correct_counts(self):
        statuses = ["PASS"] * 4 + ["FAILED"] + ["SKIPPED"] * 8
        with mock.patch.object(
            subject.daily_research_pipeline,
            "run_daily_research_pipeline",
            return_value=pipeline_result(statuses),
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                code = subject.main([])
        self.assertEqual(code, 1)
        rendered = output.getvalue()
        self.assertIn("PASS:\n4", rendered)
        self.assertIn("FAILED:\n1", rendered)
        self.assertIn("SKIPPED:\n8", rendered)

    def test_external_report_path_is_printed_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "status.csv"
            with mock.patch.object(
                subject.daily_research_pipeline,
                "run_daily_research_pipeline",
                return_value=pipeline_result(output_path=path),
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    subject.main([])
            self.assertIn(str(path), output.getvalue())

    def test_cli_contains_no_research_calculations(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("def calculate_", source)
        self.assertNotIn("to_csv", source)
        self.assertNotIn("read_csv", source)


if __name__ == "__main__":
    unittest.main()
