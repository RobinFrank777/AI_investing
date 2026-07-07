from datetime import datetime
from pathlib import Path
from config import REPORTS_DIR as CONFIG_REPORTS_DIR

REPORTS_DIR = Path(CONFIG_REPORTS_DIR)

REQUIRED_SECTIONS = [
    "AI INVESTING DAILY DECISION REPORT",
    "PART 1 - DAILY TECHNICAL SCREENING REPORT",
    "PART 2 - PORTFOLIO ACTION REPORT",
    "FINAL REMINDER",
]

REQUIRED_WARNINGS = [
    "Manual review required before any real trade",
    "No real brokerage order is placed by this system",
    "All trades must be reviewed before execution",
]


def get_today_decision_report_path():
    today = datetime.now().strftime("%Y-%m-%d")
    return REPORTS_DIR / f"daily_decision_report_{today}.txt"


def validate_daily_decision_report_outputs():
    report_path = get_today_decision_report_path()
    errors = []

    if not report_path.exists():
        errors.append(f"Missing daily decision report: {report_path}")
    else:
        report_text = report_path.read_text(encoding="utf-8")

        for section in REQUIRED_SECTIONS:
            if section not in report_text:
                errors.append(f"Missing required section: {section}")

        for warning in REQUIRED_WARNINGS:
            if warning not in report_text:
                errors.append(f"Missing required warning: {warning}")

        if "Daily Report Source" not in report_text:
            errors.append("Missing Daily Report Source line")

        if "Action Report Source" not in report_text:
            errors.append("Missing Action Report Source line")

    print("=" * 80)
    print("DAILY DECISION REPORT OUTPUT VALIDATION")
    print("=" * 80)
    print(f"Decision report file : {report_path}")

    print("\nSections checked:")
    for section in REQUIRED_SECTIONS:
        print(f"- {section}")

    print("\nWarnings checked:")
    for warning in REQUIRED_WARNINGS:
        print(f"- {warning}")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise ValueError("Daily decision report output validation failed")

    print("\nVALIDATION PASSED")
    print("Daily decision report output is valid.")


if __name__ == "__main__":
    validate_daily_decision_report_outputs()