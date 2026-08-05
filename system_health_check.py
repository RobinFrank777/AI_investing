import csv
from pathlib import Path

from config import (
    DATA_DIR_PATH,
    RESULTS_DIR_PATH,
    REPORTS_DIR_PATH,
    LOGS_DIR_PATH,
    FUNDAMENTALS_EXAMPLE_PATH,
    FUNDAMENTAL_INPUT_PATH,
    REPO_ROOT,
    WATCHLIST_EXAMPLE_PATH,
    WATCHLIST_INPUT_PATH,
)


REQUIRED_CORE_FILES = [
    "run_all.py",
    "run_daily.py",
    "run_backtest.py",
    "run_portfolio.py",
    "portfolio_risk.py",
    "position_sizing.py",
    "order_draft.py",
    "order_review.py",
    "portfolio_action_report.py",
    "daily_decision_report.py",
    "fundamental_scoring.py",
    "combined_scoring.py",
    "system_health_check.py",
    "system_version.py",
]

REQUIRED_VALIDATION_FILES = [
    "validate_config.py",
    "validate_fundamental_outputs.py",
    "validate_combined_outputs.py",
    "validate_backtest_outputs.py",
    "validate_portfolio_outputs.py",
    "validate_position_sizing_outputs.py",
    "validate_order_draft_outputs.py",
    "validate_order_review_outputs.py",
    "validate_daily_decision_report_outputs.py",
]

REQUIRED_TEST_FILES = [
    "config_validation_failure_demo.py",
    "pipeline_smoke_test.py",
]

RECOVERY_TEMPLATE_HEADERS = {
    WATCHLIST_EXAMPLE_PATH: ["Ticker"],
    FUNDAMENTALS_EXAMPLE_PATH: [
        "Ticker",
        "RevenueGrowth",
        "EPSGrowth",
        "GrossMargin",
        "OperatingMargin",
        "ROE",
        "FreeCashFlowMargin",
        "DebtToEquity",
        "PE",
        "PS",
    ],
}

RUNTIME_DIRS = [
    DATA_DIR_PATH,
    RESULTS_DIR_PATH,
    REPORTS_DIR_PATH,
    LOGS_DIR_PATH,
]

MANUAL_INPUTS = {
    WATCHLIST_INPUT_PATH: WATCHLIST_EXAMPLE_PATH,
    FUNDAMENTAL_INPUT_PATH: FUNDAMENTALS_EXAMPLE_PATH,
}


def check_files(file_names):
    return [file_name for file_name in file_names if not (REPO_ROOT / file_name).is_file()]


def read_csv_header(file_path):
    try:
        with file_path.open("r", encoding="utf-8", newline="") as file:
            return next(csv.reader(file), None)
    except (OSError, UnicodeError, csv.Error):
        return None


def check_recovery_templates():
    errors = []

    for template_path, expected_header in RECOVERY_TEMPLATE_HEADERS.items():
        if not template_path.is_file():
            errors.append(f"Missing recovery template: {template_path}")
            continue

        actual_header = read_csv_header(template_path)
        if actual_header != expected_header:
            errors.append(
                f"Recovery template header mismatch: {template_path} | "
                f"expected {expected_header} | found {actual_header}"
            )

    return errors


def get_runtime_readiness():
    return {directory: directory.is_dir() for directory in RUNTIME_DIRS}


def get_manual_input_readiness():
    return {
        input_path: {
            "ready": input_path.is_file(),
            "template": template_path,
        }
        for input_path, template_path in MANUAL_INPUTS.items()
    }


def run_system_health_check():
    core_file_errors = check_files(REQUIRED_CORE_FILES)
    validation_file_errors = check_files(REQUIRED_VALIDATION_FILES)
    test_file_errors = check_files(REQUIRED_TEST_FILES)
    template_errors = check_recovery_templates()
    runtime_readiness = get_runtime_readiness()
    manual_input_readiness = get_manual_input_readiness()

    print("=" * 80)
    print("AI INVESTING SYSTEM HEALTH CHECK")
    print("=" * 80)

    print("\nRequired files checked:")
    for file_name in REQUIRED_CORE_FILES:
        print(f"- Core: {file_name}")
    for file_name in REQUIRED_VALIDATION_FILES:
        print(f"- Validation: {file_name}")
    for file_name in REQUIRED_TEST_FILES:
        print(f"- Test: {file_name}")

    print("\nRecovery templates checked:")
    for template_path in RECOVERY_TEMPLATE_HEADERS:
        print(f"- {template_path}")

    print("\nRuntime directory readiness:")
    for directory, ready in runtime_readiness.items():
        status = "READY" if ready else "NOT PRESENT"
        print(f"- {directory}: {status}")

    print("\nManual input readiness:")
    for input_path, readiness in manual_input_readiness.items():
        status = "READY" if readiness["ready"] else "NOT READY"
        print(f"- {input_path}: {status} | recovery: {readiness['template']}")

    errors = []
    errors.extend(f"Missing core source file: {item}" for item in core_file_errors)
    errors.extend(
        f"Missing validation file: {item}" for item in validation_file_errors
    )
    errors.extend(f"Missing test file: {item}" for item in test_file_errors)
    errors.extend(template_errors)

    if errors:
        print("\nREPOSITORY HEALTH: FAILED")
        for error in errors:
            print(f"- {error}")
        raise ValueError("System health check failed")

    runtime_dirs_ready = all(runtime_readiness.values())
    manual_inputs_ready = all(
        readiness["ready"] for readiness in manual_input_readiness.values()
    )

    print("\nREPOSITORY HEALTH: PASSED")
    if runtime_dirs_ready and manual_inputs_ready:
        print("RUNTIME READINESS: READY")
    else:
        print("RUNTIME READINESS: NOT READY")
        if not runtime_dirs_ready:
            print("Create the missing runtime directories before running pipelines.")
        if not manual_inputs_ready:
            print(
                "Restore and maintain the missing manual inputs before running "
                "pipelines."
            )


if __name__ == "__main__":
    run_system_health_check()
