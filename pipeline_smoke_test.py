from datetime import datetime
from pathlib import Path
import subprocess
import sys

from config import (
    PROJECT_VERSION,
    STOCK_RANK_OUTPUT,
    TOP10_OUTPUT,
    MODEL_PORTFOLIO_OUTPUT,
    POSITION_SIZING_OUTPUT,
    ORDER_DRAFT_OUTPUT,
    ORDER_REVIEW_OUTPUT,
    PORTFOLIO_ACTION_REPORT_OUTPUT,
    SYSTEM_VERSION_OUTPUT,
    DAILY_DECISION_REPORT_PREFIX,
)


def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def run_command(command_args):
    print_section("Running command")
    print(" ".join(command_args))

    result = subprocess.run(command_args)

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            f"{' '.join(command_args)}"
        )

    print(f"Command passed: {' '.join(command_args)}")


def get_today_decision_report_path():
    today = datetime.now().strftime("%Y-%m-%d")
    return Path(f"{DAILY_DECISION_REPORT_PREFIX}_{today}.txt")


def check_required_outputs():
    print_section("Checking required output files")

    required_outputs = [
        Path(STOCK_RANK_OUTPUT),
        Path(TOP10_OUTPUT),
        Path(MODEL_PORTFOLIO_OUTPUT),
        Path(POSITION_SIZING_OUTPUT),
        Path(ORDER_DRAFT_OUTPUT),
        Path(ORDER_REVIEW_OUTPUT),
        Path(PORTFOLIO_ACTION_REPORT_OUTPUT),
        Path(SYSTEM_VERSION_OUTPUT),
        get_today_decision_report_path(),
    ]

    missing_outputs = []

    for output_path in required_outputs:
        if output_path.exists():
            print(f"- FOUND: {output_path}")
        else:
            print(f"- MISSING: {output_path}")
            missing_outputs.append(output_path)

    if missing_outputs:
        missing_text = "\n".join(f"- {path}" for path in missing_outputs)
        raise FileNotFoundError(
            "Smoke test failed. Missing required output files:\n"
            f"{missing_text}"
        )

    print("\nAll required output files were found.")


def run_pipeline_smoke_test():
    print_section("AI INVESTING PIPELINE SMOKE TEST")
    print(f"Project version checked: {PROJECT_VERSION}")
    print("This smoke test runs validation and the full portfolio pipeline.")
    print("It does not place trades.")
    print("It does not connect to a brokerage account.")

    run_command([sys.executable, "validate_config.py"])
    run_command([sys.executable, "config_validation_failure_demo.py"])
    run_command([sys.executable, "run_portfolio.py"])

    check_required_outputs()

    print_section("PIPELINE SMOKE TEST PASSED")
    print("Config validation passed.")
    print("Failure demo passed.")
    print("Full portfolio pipeline completed.")
    print("Required output files were generated.")


if __name__ == "__main__":
    run_pipeline_smoke_test()