from datetime import datetime
from pathlib import Path
from config import (
    PORTFOLIO_ACTION_REPORT_OUTPUT as CONFIG_PORTFOLIO_ACTION_REPORT_OUTPUT,
    REPORTS_DIR as CONFIG_REPORTS_DIR,
)

REPORTS_DIR = Path(CONFIG_REPORTS_DIR)
ACTION_REPORT_INPUT = Path(CONFIG_PORTFOLIO_ACTION_REPORT_OUTPUT)


def find_latest_daily_report():
    report_files = list(REPORTS_DIR.glob("daily_trading_report_*.txt"))

    if not report_files:
        raise FileNotFoundError("No daily trading report found in reports/")

    latest_file = max(report_files, key=lambda file_path: file_path.stat().st_mtime)
    return latest_file


def read_text_file(file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"Missing input file: {file_path}")

    return file_path.read_text(encoding="utf-8")


def build_daily_decision_report():
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_date = datetime.now().strftime("%Y-%m-%d")

    latest_daily_report = find_latest_daily_report()
    daily_report_text = read_text_file(latest_daily_report)
    action_report_text = read_text_file(ACTION_REPORT_INPUT)

    lines = []

    lines.append("=" * 80)
    lines.append("AI INVESTING DAILY DECISION REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated At        : {generated_at}")
    lines.append(f"Daily Report Source : {latest_daily_report}")
    lines.append(f"Action Report Source: {ACTION_REPORT_INPUT}")
    lines.append("")
    lines.append("Decision Principle  : Manual review required before any real trade")
    lines.append("Execution Status    : No real brokerage order is placed by this system")
    lines.append("")

    lines.append("=" * 80)
    lines.append("PART 1 - DAILY TECHNICAL SCREENING REPORT")
    lines.append("=" * 80)
    lines.append(daily_report_text)
    lines.append("")

    lines.append("=" * 80)
    lines.append("PART 2 - PORTFOLIO ACTION REPORT")
    lines.append("=" * 80)
    lines.append(action_report_text)
    lines.append("")

    lines.append("=" * 80)
    lines.append("FINAL REMINDER")
    lines.append("=" * 80)
    lines.append("This report is for research and manual review only.")
    lines.append("BUY signals are candidates, not verified real trading instructions.")
    lines.append("All trades must be reviewed before execution.")

    output_path = REPORTS_DIR / f"daily_decision_report_{report_date}.txt"
    REPORTS_DIR.mkdir(exist_ok=True)

    output_text = "\n".join(lines)
    output_path.write_text(output_text, encoding="utf-8")

    return output_path


def print_daily_decision_report():
    output_path = build_daily_decision_report()
    report_text = read_text_file(output_path)

    print(report_text)
    print(f"\nSaved Daily Decision Report To : {output_path}")

    return output_path


if __name__ == "__main__":
    print_daily_decision_report()