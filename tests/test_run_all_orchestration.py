import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run_all


def ready_market_data():
    import pandas as pd

    return pd.DataFrame(
        [{"Ticker": "READY", "Ready": True, "Reason": "READY", "Status": "READY"}]
    )


class RunAllOrchestrationTests(unittest.TestCase):
    def run_silently(self, steps):
        output = io.StringIO()
        context = {
            "CurrentRunId": "test-attempt", "AsOfDate": "2026-08-12",
            "OverallRunStatus": "RUNNING",
        }
        with (
            redirect_stdout(output),
            patch.object(run_all, "start_current_run", return_value=context),
            patch.object(
                run_all, "finish_current_run",
                side_effect=lambda current, **changes: {**current, **changes},
            ),
            patch.object(run_all, "write_failed_current_reports"),
            patch.object(
                run_all, "_successful_candidate_identity",
                return_value=("test-candidate", "2026-08-12"),
            ),
        ):
            exit_code = run_all.run_pipeline(steps)
        return exit_code, output.getvalue()

    def test_success_flow_preserves_step_order_and_returns_zero(self):
        calls = []
        steps = [
            {"name": "first", "action": lambda: calls.append("first")},
            {"name": "second", "action": lambda: calls.append("second")},
        ]

        exit_code, output = self.run_silently(steps)

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, ["first", "second"])
        self.assertIn("Status      : PASS", output)

    def test_producer_failure_stops_required_downstream_step(self):
        calls = []

        def fail():
            raise RuntimeError("producer failed")

        steps = [
            {"name": "producer", "action": fail},
            {"name": "downstream", "action": lambda: calls.append("downstream")},
        ]

        exit_code, output = self.run_silently(steps)

        self.assertEqual(exit_code, 1)
        self.assertEqual(calls, [])
        self.assertIn("RuntimeError", output)
        self.assertIn("SKIP", output)

    def test_validator_failure_returns_one(self):
        def fail_validation():
            raise ValueError("validator failed")

        steps = [
            {
                "name": "validated producer",
                "action": lambda: None,
                "validator": fail_validation,
            }
        ]

        exit_code, output = self.run_silently(steps)

        self.assertEqual(exit_code, 1)
        self.assertIn("validator failed", output)

    def test_missing_artifact_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "missing.csv"
            steps = [
                {"name": "producer", "action": lambda: None, "artifacts": (artifact,)}
            ]

            exit_code, output = self.run_silently(steps)

        self.assertEqual(exit_code, 1)
        self.assertIn("was not produced", output)

    def test_stale_artifact_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "stale.csv"
            artifact.write_text("value\n1\n", encoding="utf-8")
            steps = [
                {"name": "producer", "action": lambda: None, "artifacts": (artifact,)}
            ]

            exit_code, output = self.run_silently(steps)

        self.assertEqual(exit_code, 1)
        self.assertIn("was not updated", output)

    def test_updated_nonempty_artifact_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "fresh.csv"

            def produce():
                artifact.write_text("value\n1\n", encoding="utf-8")

            steps = [
                {"name": "producer", "action": produce, "artifacts": (artifact,)}
            ]

            exit_code, _ = self.run_silently(steps)

        self.assertEqual(exit_code, 0)

    def test_empty_artifact_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "empty.csv"

            def produce():
                artifact.write_text("", encoding="utf-8")

            steps = [
                {"name": "producer", "action": produce, "artifacts": (artifact,)}
            ]

            exit_code, output = self.run_silently(steps)

        self.assertEqual(exit_code, 1)
        self.assertIn("is empty", output)

    def test_summary_contains_research_only_warning(self):
        exit_code, output = self.run_silently(
            [{"name": "only step", "action": lambda: None}]
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("research outputs only", output)
        self.assertIn("not investment approval", output)
        self.assertIn("No brokerage order was submitted", output)

    def test_known_insufficient_history_is_excluded_without_blocking_pipeline(self):
        results = [
            {
                "Ticker": "READY",
                "IsValid": True,
                "Errors": [],
                "Warnings": [],
                "LatestDate": "2026-08-13",
            },
            {
                "Ticker": "SKHY",
                "IsValid": False,
                "Errors": [
                    "Insufficient history: 25 rows; at least 252 required."
                ],
                "Warnings": [],
                "LatestDate": "2026-08-13",
            },
        ]
        output = io.StringIO()
        with (
            patch.object(
                run_all, "validate_watchlist", return_value=(results, "2026-08-13")
            ),
            patch.object(run_all, "print_validation_summary"),
            patch.object(run_all, "build_data_readiness", return_value=pd.DataFrame([
                {"Ticker": "READY", "Ready": True, "Reason": "READY", "Status": "READY"},
                {"Ticker": "SKHY", "Ready": False, "Reason": "INSUFFICIENT_HISTORY", "Status": "INSUFFICIENT_HISTORY"},
            ])),
            patch.object(run_all, "save_data_readiness"),
            redirect_stdout(output),
        ):
            run_all.validate_market_data()
        self.assertIn("SKHY", output.getvalue())
        self.assertIn("INSUFFICIENT_HISTORY", output.getvalue())

    def test_structural_market_data_failure_still_blocks_pipeline(self):
        results = [
            {
                "Ticker": "BROKEN",
                "IsValid": False,
                "Errors": ["Missing required columns: ['Close']"],
                "Warnings": [],
                "LatestDate": "2026-08-13",
            }
        ]
        with (
            patch.object(
                run_all, "validate_watchlist", return_value=(results, "2026-08-13")
            ),
            patch.object(run_all, "print_validation_summary"),
            patch.object(run_all, "build_data_readiness", return_value=pd.DataFrame([{
                "Ticker": "BROKEN", "Ready": False,
                "Reason": "MISSING_COLUMNS", "Status": "INVALID_CANONICAL_DATA",
            }])),
            patch.object(run_all, "save_data_readiness"),
            self.assertRaisesRegex(RuntimeError, "BROKEN"),
        ):
            run_all.validate_market_data()

    def test_stale_market_data_is_quarantined_without_blocking_ready_subset(self):
        results = [
            {
                "Ticker": "STALE",
                "IsValid": True,
                "Errors": [],
                "Warnings": [
                    "Latest date 2026-08-12 is behind universe latest date 2026-08-13."
                ],
                "LatestDate": "2026-08-12",
            }
        ]
        with (
            patch.object(
                run_all, "validate_watchlist", return_value=(results, "2026-08-13")
            ),
            patch.object(run_all, "print_validation_summary"),
            patch.object(run_all, "build_data_readiness", return_value=pd.DataFrame([
                {"Ticker": "READY", "Ready": True, "Reason": "READY", "Status": "READY"},
                {"Ticker": "STALE", "Ready": False, "Reason": "STALE_MARKET_DATA", "Status": "STALE_MARKET_DATA"},
            ])),
            patch.object(run_all, "save_data_readiness"),
            redirect_stdout(io.StringIO()) as output,
        ):
            run_all.validate_market_data()
        self.assertIn("STALE (STALE_MARKET_DATA)", output.getvalue())

    def test_refresh_failure_defers_to_following_validation(self):
        with patch.object(
            run_all,
            "update_all_stocks",
            return_value={
                "succeeded": 149,
                "failed": 1,
                "failed_symbols": ["OXY"],
            },
        ):
            result = run_all.update_market_data()
        self.assertEqual(result["failed_symbols"], ["OXY"])

    def test_readiness_structural_failure_blocks_pipeline(self):
        import pandas as pd

        results = [{
            "Ticker": "KR", "IsValid": True, "Errors": [], "Warnings": [],
            "LatestDate": "2026-08-13",
        }]
        readiness = pd.DataFrame([{
            "Ticker": "KR", "Ready": False, "Reason": "INVALID_OHLC",
            "Status": "INVALID_CANONICAL_DATA",
        }])
        with (
            patch.object(run_all, "validate_watchlist", return_value=(results, "2026-08-13")),
            patch.object(run_all, "print_validation_summary"),
            patch.object(run_all, "build_data_readiness", return_value=readiness),
            patch.object(run_all, "save_data_readiness"),
            self.assertRaisesRegex(RuntimeError, "KR \\(INVALID_OHLC\\)"),
        ):
            run_all.validate_market_data()

    def test_all_symbols_unavailable_still_blocks_pipeline(self):
        import pandas as pd

        readiness = pd.DataFrame([{
            "Ticker": "STALE", "Ready": False,
            "Reason": "STALE_MARKET_DATA", "Status": "STALE_MARKET_DATA",
        }])
        with (
            patch.object(run_all, "validate_watchlist", return_value=([], None)),
            patch.object(run_all, "print_validation_summary"),
            patch.object(run_all, "build_data_readiness", return_value=readiness),
            patch.object(run_all, "save_data_readiness"),
            self.assertRaisesRegex(RuntimeError, "no READY symbols"),
        ):
            run_all.validate_market_data()

    def test_sanitizer_hides_repository_and_home_paths(self):
        repo_message = f"input: {run_all.REPO_ROOT}/data/watchlist.csv"
        home_message = f"cache: {Path.home()}/private-cache"

        self.assertNotIn(str(run_all.REPO_ROOT), run_all.sanitize_text(repo_message))
        self.assertNotIn(str(Path.home()), run_all.sanitize_text(home_message))


if __name__ == "__main__":
    unittest.main()
