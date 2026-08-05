import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run_all


class RunAllOrchestrationTests(unittest.TestCase):
    def run_silently(self, steps):
        output = io.StringIO()
        with redirect_stdout(output):
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

    def test_sanitizer_hides_repository_and_home_paths(self):
        repo_message = f"input: {run_all.REPO_ROOT}/data/watchlist.csv"
        home_message = f"cache: {Path.home()}/private-cache"

        self.assertNotIn(str(run_all.REPO_ROOT), run_all.sanitize_text(repo_message))
        self.assertNotIn(str(Path.home()), run_all.sanitize_text(home_message))


if __name__ == "__main__":
    unittest.main()
