from pathlib import Path


REQUIRED_SOURCE_FILES = [
    "run_daily.py",
    "run_backtest.py",
    "run_portfolio.py",
    "portfolio_risk.py",
    "position_sizing.py",
    "order_draft.py",
    "order_review.py",
    "portfolio_action_report.py",
    "daily_decision_report.py",
    "validate_backtest_outputs.py",
    "validate_portfolio_outputs.py",
    "validate_position_sizing_outputs.py",
    "validate_order_draft_outputs.py",
    "validate_order_review_outputs.py",
    "validate_daily_decision_report_outputs.py",
]

REQUIRED_DIRS = [
    "data",
    "results",
    "reports",
    "logs",
]

REQUIRED_GITIGNORE_RULES = [
    "data/*.csv",
    "results/",
    "reports/daily_trading_report_*.txt",
    "logs/",
]


def check_files():
    missing = []

    for file_name in REQUIRED_SOURCE_FILES:
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
    file_errors = check_files()
    dir_errors = check_dirs()
    gitignore_errors = check_gitignore()

    print("=" * 80)
    print("AI INVESTING SYSTEM HEALTH CHECK")
    print("=" * 80)

    print("\nSource files checked:")
    for file_name in REQUIRED_SOURCE_FILES:
        print(f"- {file_name}")

    print("\nDirectories checked:")
    for dir_name in REQUIRED_DIRS:
        print(f"- {dir_name}")

    print("\n.gitignore rules checked:")
    for rule in REQUIRED_GITIGNORE_RULES:
        print(f"- {rule}")

    errors = []

    for item in file_errors:
        errors.append(f"Missing source file: {item}")

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