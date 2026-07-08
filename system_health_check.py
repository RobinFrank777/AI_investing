from pathlib import Path
from config import (
    DATA_DIR as CONFIG_DATA_DIR,
    RESULTS_DIR as CONFIG_RESULTS_DIR,
    REPORTS_DIR as CONFIG_REPORTS_DIR,
    LOGS_DIR as CONFIG_LOGS_DIR,
)

REQUIRED_CORE_FILES = [
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
    "system_health_check.py",
    "system_version.py",
]

REQUIRED_VALIDATION_FILES = [
    "validate_config.py",
    "validate_fundamental_outputs.py",
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

REQUIRED_DIRS = [
    Path(CONFIG_DATA_DIR),
    Path(CONFIG_RESULTS_DIR),
    Path(CONFIG_REPORTS_DIR),
    Path(CONFIG_LOGS_DIR),
]

REQUIRED_GITIGNORE_RULES = [
    "data/*.csv",
    "results/",
    "reports/daily_trading_report_*.txt",
    "logs/",
]


def check_files(file_names):
    missing = []

    for file_name in file_names:
        file_path = Path(file_name)

        if not file_path.exists():
            missing.append(file_name)

    return missing


def check_dirs():
    missing = []

    for dir_name in REQUIRED_DIRS:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            missing.append(dir_name)

    return missing


def check_gitignore():
    gitignore_path = Path(".gitignore")
    missing = []

    if not gitignore_path.exists():
        return REQUIRED_GITIGNORE_RULES

    gitignore_text = gitignore_path.read_text(encoding="utf-8")

    for rule in REQUIRED_GITIGNORE_RULES:
        if rule not in gitignore_text:
            missing.append(rule)

    return missing


def run_system_health_check():
    core_file_errors = check_files(REQUIRED_CORE_FILES)
    validation_file_errors = check_files(REQUIRED_VALIDATION_FILES)
    test_file_errors = check_files(REQUIRED_TEST_FILES)
    dir_errors = check_dirs()
    gitignore_errors = check_gitignore()

    print("=" * 80)
    print("AI INVESTING SYSTEM HEALTH CHECK")
    print("=" * 80)

    print("\nCore source files checked:")
    for file_name in REQUIRED_CORE_FILES:
        print(f"- {file_name}")

    print("\nValidation files checked:")
    for file_name in REQUIRED_VALIDATION_FILES:
        print(f"- {file_name}")

    print("\nTest files checked:")
    for file_name in REQUIRED_TEST_FILES:
        print(f"- {file_name}")

    print("\nDirectories checked:")
    for dir_name in REQUIRED_DIRS:
        print(f"- {dir_name}")

    print("\n.gitignore rules checked:")
    for rule in REQUIRED_GITIGNORE_RULES:
        print(f"- {rule}")

    errors = []

    for item in core_file_errors:
        errors.append(f"Missing core source file: {item}")

    for item in validation_file_errors:
        errors.append(f"Missing validation file: {item}")

    for item in test_file_errors:
        errors.append(f"Missing test file: {item}")

    for item in dir_errors:
        errors.append(f"Missing directory: {item}")

    for item in gitignore_errors:
        errors.append(f"Missing .gitignore rule: {item}")

    if errors:
        print("\nHEALTH CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        raise ValueError("System health check failed")

    print("\nHEALTH CHECK PASSED")
    print("AI_investing system structure is valid.")


if __name__ == "__main__":
    run_system_health_check()