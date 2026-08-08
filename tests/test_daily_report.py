import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from config import PROJECT_VERSION


ENTRY_PATH = Path(__file__).resolve().parents[1] / "daily_report.py"


def _load_entry():
    spec = importlib.util.spec_from_file_location("daily_report_entry", ENTRY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DailyReportEntryTests(unittest.TestCase):
    def test_release_metadata(self):
        entry = _load_entry()
        self.assertEqual(PROJECT_VERSION, entry.VERSION)
        self.assertEqual("Phase 9L Step 7", entry.CURRENT_PHASE)
        self.assertRegex(entry.REPORT_DATE, r"^\d{4}-\d{2}-\d{2}$")

    def test_main_generates_user_outputs_in_dependency_order(self):
        entry = _load_entry()
        calls = []
        with (
            patch.object(entry, "generate_risk_alerts", side_effect=lambda: calls.append("alerts") or {"output_path": "results/risk_alerts.csv"}),
            patch.object(entry, "generate_daily_dashboard", side_effect=lambda: calls.append("dashboard") or {"output_path": "results/daily_dashboard.html"}),
            patch.object(entry, "generate_daily_report", side_effect=lambda: calls.append("report") or {"report_path": "results/daily_investment_report.md"}),
        ):
            self.assertEqual(0, entry.main())
        self.assertEqual(["alerts", "dashboard", "report"], calls)

    def test_main_returns_nonzero_without_traceback_on_failure(self):
        entry = _load_entry()
        with patch.object(entry, "generate_risk_alerts", side_effect=OSError("unavailable")):
            self.assertEqual(1, entry.main())


if __name__ == "__main__":
    unittest.main()
