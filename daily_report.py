"""Official user entry point for AI_investing daily research outputs."""

import sys
from datetime import date

from config import PROJECT_VERSION
from daily_dashboard import generate_daily_dashboard
from daily_report.generator import generate_daily_report
from risk_alert_module import generate_risk_alerts


VERSION = PROJECT_VERSION
CURRENT_PHASE = "Phase 9L Step 7"
REPORT_DATE = date.today().isoformat()


def main():
    """Generate the three user-layer daily research artifacts."""
    try:
        alerts = generate_risk_alerts()
        dashboard = generate_daily_dashboard()
        report = generate_daily_report()
    except (OSError, TypeError, ValueError) as error:
        print(f"Daily report generation failed: {error}", file=sys.stderr)
        return 1

    print("AI_investing Daily Report")
    print(f"Version: {VERSION}")
    print(f"Phase: {CURRENT_PHASE}")
    print(f"Report Date: {REPORT_DATE}")
    print(f"Markdown: {report['report_path']}")
    print(f"Dashboard: {dashboard['output_path']}")
    print(f"Risk Alerts: {alerts['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
