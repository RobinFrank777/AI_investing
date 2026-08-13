import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import config
import report_artifact_consistency as reports
import run_all
from current_run_status import finish_current_run, start_current_run


class CurrentRunReportTruthfulnessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.status_path = self.root / "current_run_status.json"
        self.candidate_path = self.root / "candidate.csv"

    def write_candidate(self, run_id, as_of="2026-08-13"):
        pd.DataFrame(
            {
                "Ticker": ["AAA"],
                "Eligibility": ["INELIGIBLE"],
                "TradeSignal": ["WATCH"],
                "RunId": [run_id],
                "AsOfDate": [as_of],
                "UniverseVersion": [config.PRIMARY_UNIVERSE_VERSION],
                "ScoreModelVersion": ["technical-score-v3.8.1-r1"],
            }
        ).to_csv(self.candidate_path, index=False)

    def assess(self):
        return reports.assess_current_report(
            {"Production Candidate": self.candidate_path},
            report_date="2026-08-13",
            run_status_path=self.status_path,
        )

    def test_same_day_later_failure_supersedes_prior_no_action(self):
        self.write_candidate("run-a")
        run_a = start_current_run(self.status_path)
        finish_current_run(
            run_a, status="PASS", current_run_id="run-a",
            as_of_date="2026-08-13", path=self.status_path,
        )
        self.assertEqual(self.assess().status, reports.NO_ACTION)

        run_b = start_current_run(self.status_path)
        finish_current_run(
            run_b, status="FAILED", failed_stage="Market data validation",
            reason="INVALID_OHLC", path=self.status_path,
        )
        result = self.assess()
        self.assertEqual(result.status, reports.FAILED)
        self.assertEqual(result.metadata["RunId"], run_b["CurrentRunId"])
        self.assertNotEqual(result.metadata["RunId"], "run-a")

    def test_success_context_must_match_artifact_run_id(self):
        self.write_candidate("artifact-run")
        context = start_current_run(self.status_path)
        finish_current_run(
            context, status="PASS", current_run_id="different-run",
            as_of_date="2026-08-13", path=self.status_path,
        )
        self.assertEqual(self.assess().status, reports.INCOMPATIBLE)

    def test_previous_day_artifact_cannot_be_current(self):
        self.write_candidate("run-a", as_of="2026-08-12")
        context = start_current_run(self.status_path)
        finish_current_run(
            context, status="PASS", current_run_id="run-a",
            as_of_date="2026-08-13", path=self.status_path,
        )
        self.assertEqual(self.assess().status, reports.STALE)

    def test_failed_run_never_falls_back_to_candidate_or_backtest(self):
        self.write_candidate("old-success")
        context = start_current_run(self.status_path)
        finish_current_run(
            context, status="FAILED", failed_stage="Preflight", reason="failed",
            path=self.status_path,
        )
        result = self.assess()
        self.assertEqual(result.status, reports.FAILED)
        self.assertNotIn("backtest", " ".join(result.reasons).lower())

    def test_failed_attempt_replaces_current_report_paths_with_failure_evidence(self):
        action = self.root / "portfolio_action.txt"
        decision = self.root / "daily_decision.txt"
        context = {
            "CurrentRunId": "run-b", "AsOfDate": "2026-08-12",
            "FailedStage": "Market data validation",
            "FailureReason": "INVALID_OHLC",
        }
        with (
            patch.object(run_all, "PORTFOLIO_ACTION_REPORT_OUTPUT_PATH", action),
            patch.object(run_all, "daily_decision_report_path", return_value=decision),
        ):
            run_all.write_failed_current_reports(context)
        for path in (action, decision):
            text = path.read_text(encoding="utf-8")
            self.assertIn("FAILED", text)
            self.assertIn("run-b", text)
            self.assertNotIn("NO_ACTION", text)


if __name__ == "__main__":
    unittest.main()
