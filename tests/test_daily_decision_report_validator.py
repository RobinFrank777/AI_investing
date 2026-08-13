import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_daily_decision_report_outputs as subject


class DailyDecisionReportValidatorTests(unittest.TestCase):
    def test_truthful_current_report_sections_validate(self):
        with tempfile.TemporaryDirectory() as root:
            report = Path(root) / "daily_decision_report.txt"
            report.write_text(
                "\n".join(
                    subject.REQUIRED_SECTIONS
                    + subject.REQUIRED_WARNINGS
                    + ["Daily Report Source", "Action Report Source"]
                ),
                encoding="utf-8",
            )
            with patch.object(
                subject, "get_today_decision_report_path", return_value=report
            ):
                subject.validate_daily_decision_report_outputs()

    def test_legacy_unlabeled_research_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            report = Path(root) / "daily_decision_report.txt"
            report.write_text(
                "\n".join(
                    [
                        "AI INVESTING DAILY DECISION REPORT",
                        "PART 1 - DAILY TECHNICAL SCREENING REPORT",
                        "PART 2 - PORTFOLIO ACTION REPORT",
                        "FINAL REMINDER",
                    ]
                    + subject.REQUIRED_WARNINGS
                    + ["Daily Report Source", "Action Report Source"]
                ),
                encoding="utf-8",
            )
            with (
                patch.object(
                    subject, "get_today_decision_report_path", return_value=report
                ),
                self.assertRaisesRegex(ValueError, "validation failed"),
            ):
                subject.validate_daily_decision_report_outputs()


if __name__ == "__main__":
    unittest.main()
