from datetime import datetime
from pathlib import Path
import subprocess
import sys

from config import (
    PROJECT_VERSION,
    SYSTEM_VERSION_OUTPUT as CONFIG_SYSTEM_VERSION_OUTPUT,
)


OUTPUT_FILE = Path(CONFIG_SYSTEM_VERSION_OUTPUT)


CORE_MODULES = [
    "run_daily.py",
    "run_backtest.py",
    "run_portfolio.py",
    "portfolio_risk.py",
    "position_sizing.py",
    "order_draft.py",
    "order_review.py",
    "portfolio_action_report.py",
    "daily_decision_report.py",
    "system_health_check.py",
]


VALIDATION_MODULES = [
    "validate_config.py",
    "validate_backtest_outputs.py",
    "validate_portfolio_outputs.py",
    "validate_position_sizing_outputs.py",
    "validate_order_draft_outputs.py",
    "validate_order_review_outputs.py",
    "validate_daily_decision_report_outputs.py",
]


def get_git_value(command_args, default_value="UNKNOWN"):
    try:
        result = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return default_value


def get_project_version():
    return get_git_value(
        ["git", "describe", "--tags", "--abbrev=0"],
        default_value="NO_TAG_FOUND",
    )


def get_git_branch():
    return get_git_value(
        ["git", "branch", "--show-current"],
        default_value="UNKNOWN_BRANCH",
    )


def get_git_commit():
    return get_git_value(
        ["git", "rev-parse", "--short", "HEAD"],
        default_value="UNKNOWN_COMMIT",
    )


def build_system_version_text():
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    project_version = PROJECT_VERSION
    git_branch = get_git_branch()
    git_commit = get_git_commit()
    python_version = sys.version.split()[0]

    lines = []

    lines.append("=" * 80)
    lines.append("AI INVESTING SYSTEM VERSION REPORT")
    lines.append("=" * 80)

    lines.append("")
    lines.append(f"Generated At     : {generated_at}")
    lines.append(f"Project Version  : {project_version}")
    lines.append(f"Git Branch       : {git_branch}")
    lines.append(f"Git Commit       : {git_commit}")
    lines.append(f"Python Version   : {python_version}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("CORE MODULES")
    lines.append("=" * 80)

    for module_name in CORE_MODULES:
        module_path = Path(module_name)
        status = "FOUND" if module_path.exists() else "MISSING"
        lines.append(f"- {module_name}: {status}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("VALIDATION MODULES")
    lines.append("=" * 80)

    for module_name in VALIDATION_MODULES:
        module_path = Path(module_name)
        status = "FOUND" if module_path.exists() else "MISSING"
        lines.append(f"- {module_name}: {status}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("SYSTEM NOTE")
    lines.append("=" * 80)
    lines.append("This report records the current AI_investing system version.")
    lines.append("It does not place trades.")
    lines.append("It is used for system tracking, debugging, and release review.")

    return "\n".join(lines)


def print_system_version():
    version_text = build_system_version_text()

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(version_text, encoding="utf-8")

    print(version_text)
    print("")
    print(f"Saved System Version Report To : {OUTPUT_FILE}")


if __name__ == "__main__":
    print_system_version()