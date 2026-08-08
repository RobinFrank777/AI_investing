import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import daily_research_pipeline as subject


class DailyResearchPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "results" / "status.csv"
        log_patch = mock.patch.object(
            subject.research_pipeline_logger,
            "save_pipeline_log",
            return_value=self.root / "pipeline.json",
        )
        self.log_writer = log_patch.start()
        self.addCleanup(log_patch.stop)

    @staticmethod
    def successful_steps(calls=None):
        functions = {}
        for name in subject.STEP_NAMES:
            def run(step_name=name):
                if calls is not None:
                    calls.append(step_name)
                if step_name == "ResearchDatasetValidator":
                    return pd.DataFrame(
                        {
                            "CheckItem": ["OverallStatus"],
                            "Value": ["PASS"],
                            "Status": ["PASS"],
                        }
                    )
                return {"ok": True}

            functions[name] = run
        return functions

    def test_all_steps_pass_in_fixed_sequence(self):
        calls = []
        result = subject.run_daily_research_pipeline(
            output_path=self.output,
            run_date="2026-08-08",
            step_functions=self.successful_steps(calls),
        )
        self.assertEqual(calls, list(subject.STEP_NAMES))
        self.assertEqual(result["status"]["Status"].tolist(), ["PASS"] * 13)
        self.assertEqual(result["status"]["StepName"].tolist(), list(subject.STEP_NAMES))
        self.log_writer.assert_called_once()

    def test_single_step_failure_is_recorded(self):
        functions = self.successful_steps()

        def fail():
            raise FileNotFoundError("factor file missing")

        functions["FactorRanking"] = fail
        result = subject.run_daily_research_pipeline(
            output_path=self.output, step_functions=functions
        )["status"].set_index("StepName")
        self.assertEqual(result.at["UniverseFactorRunner", "Status"], "PASS")
        self.assertEqual(result.at["FactorRanking", "Status"], "FAILED")
        self.assertEqual(result.at["FactorRanking", "Message"], "factor file missing")

    def test_steps_after_failure_are_skipped(self):
        calls = []
        functions = self.successful_steps(calls)

        def fail():
            calls.append("SignalEngine")
            raise RuntimeError("signal artifact unavailable")

        functions["SignalEngine"] = fail
        status = subject.run_daily_research_pipeline(
            output_path=self.output, step_functions=functions
        )["status"]
        self.assertEqual(calls, list(subject.STEP_NAMES[:4]))
        self.assertEqual(status.loc[3, "Status"], "FAILED")
        self.assertTrue((status.loc[4:, "Status"] == "SKIPPED").all())
        self.assertTrue(
            status.loc[4:, "Message"].str.contains("SignalEngine").all()
        )

    def test_output_csv_has_fixed_fields(self):
        result = subject.run_daily_research_pipeline(
            output_path=self.output,
            run_date="2026-08-08",
            step_functions=self.successful_steps(),
        )
        saved = pd.read_csv(self.output)
        self.assertEqual(tuple(saved.columns), subject.STATUS_COLUMNS)
        self.assertEqual(saved["RunDate"].tolist(), ["2026-08-08"] * 13)
        self.assertEqual(result["output_path"], str(self.output))

    def test_empty_step_results_are_legal_passes(self):
        functions = {name: (lambda: None) for name in subject.STEP_NAMES}
        functions["ResearchDatasetValidator"] = lambda: pd.DataFrame(
            {
                "CheckItem": ["OverallStatus"],
                "Value": ["PASS"],
                "Status": ["PASS"],
            }
        )
        status = subject.run_daily_research_pipeline(
            output_path=self.output, step_functions=functions
        )["status"]
        self.assertEqual(len(status), 13)
        self.assertTrue((status["Status"] == "PASS").all())
        self.assertEqual(
            int((status["Message"] == "completed with empty result").sum()), 12
        )

    def test_default_functions_call_existing_public_entries(self):
        patches = []
        targets = (
            (subject.universe_factor_runner, "run_universe_factors"),
            (subject.factor_ranking, "run_factor_ranking"),
            (subject.research_report_builder, "run_research_report"),
            (subject.signal_engine, "run_signal_engine"),
            (subject.universe_risk_runner, "run_universe_risk"),
            (subject.risk_factor_merge, "run_risk_factor_merge"),
            (subject.research_dataset_validator, "validate_research_dataset"),
            (subject.research_candidate_selector, "run_candidate_selector"),
            (subject.candidate_report_builder, "run_candidate_report"),
            (subject.daily_research_snapshot, "run_daily_snapshot"),
            (subject.research_explanation_engine, "run_explanation_engine"),
            (subject.ai_research_summary_builder, "run_ai_research_summary_builder"),
            (subject.research_report_composer, "generate_research_report"),
        )
        for module, name in targets:
            return_value = (
                pd.DataFrame(
                    {
                        "CheckItem": ["OverallStatus"],
                        "Value": ["PASS"],
                        "Status": ["PASS"],
                    }
                )
                if name == "validate_research_dataset"
                else {"ok": True}
            )
            patches.append(mock.patch.object(module, name, return_value=return_value))
        mocks = [patch.start() for patch in patches]
        self.addCleanup(lambda: [patch.stop() for patch in patches])
        status = subject.run_daily_research_pipeline(output_path=self.output)["status"]
        self.assertTrue((status["Status"] == "PASS").all())
        self.assertTrue(all(function.call_count == 1 for function in mocks))

    def test_unknown_step_override_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UnknownStep"):
            subject.run_daily_research_pipeline(
                output_path=self.output,
                step_functions={"UnknownStep": lambda: None},
            )

    def test_failed_validator_blocks_remaining_steps(self):
        functions = self.successful_steps()
        functions["ResearchDatasetValidator"] = lambda: pd.DataFrame(
            {
                "CheckItem": ["OverallStatus"],
                "Value": ["FAILED"],
                "Status": ["FAILED"],
            }
        )
        status = subject.run_daily_research_pipeline(
            output_path=self.output, step_functions=functions
        )["status"]
        self.assertEqual(status.loc[6, "Status"], "FAILED")
        self.assertTrue((status.loc[7:, "Status"] == "SKIPPED").all())

    def test_existing_modules_are_not_modified_by_pipeline(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        self.assertNotIn("def calculate_", source)
        self.assertNotIn("def normalize_", source)
        self.assertNotIn("def rank_", source)


if __name__ == "__main__":
    unittest.main()
