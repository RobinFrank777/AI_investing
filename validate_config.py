from pathlib import Path

from config import (
    ACCOUNT_VALUE,
    ACCOUNT_SIZE,
    RISK_PER_TRADE,
    MAX_HOLDINGS,
    MAX_SINGLE_POSITION_WEIGHT,
    MAX_TOTAL_EXPOSURE,
    CASH_RESERVE_RATIO,
    LOW_RISK_WEIGHT_MULTIPLIER,
    MEDIUM_RISK_WEIGHT_MULTIPLIER,
    HIGH_RISK_WEIGHT_MULTIPLIER,
    UNKNOWN_RISK_WEIGHT_MULTIPLIER,
    MAX_ORDER_COUNT,
    MAX_TOTAL_ORDER_VALUE,
    MAX_SINGLE_ORDER_VALUE,
    ALLOWED_ACTIONS,
    ALLOWED_ORDER_STATUS,
    ALLOWED_REVIEW_STATUS,
    ALLOWED_PORTFOLIO_REVIEW_FLAG,
    DATA_DIR,
    RESULTS_DIR,
    REPORTS_DIR,
    LOGS_DIR,
    STOCK_RANK_OUTPUT,
    TOP10_OUTPUT,
    MODEL_PORTFOLIO_OUTPUT,
    POSITION_SIZING_OUTPUT,
    ORDER_DRAFT_OUTPUT,
    ORDER_REVIEW_OUTPUT,
    PORTFOLIO_ACTION_REPORT_OUTPUT,
    SYSTEM_VERSION_OUTPUT,
    DAILY_DECISION_REPORT_PREFIX,
    PROJECT_VERSION,
)


def check_positive_number(name, value, errors):
    if not isinstance(value, (int, float)):
        errors.append(f"{name} must be a number")
        return

    if value <= 0:
        errors.append(f"{name} must be greater than 0")


def check_non_negative_number(name, value, errors):
    if not isinstance(value, (int, float)):
        errors.append(f"{name} must be a number")
        return

    if value < 0:
        errors.append(f"{name} must be greater than or equal to 0")


def check_ratio(name, value, errors):
    if not isinstance(value, (int, float)):
        errors.append(f"{name} must be a number")
        return

    if value < 0 or value > 1:
        errors.append(f"{name} must be between 0 and 1")


def check_positive_integer(name, value, errors):
    if not isinstance(value, int):
        errors.append(f"{name} must be an integer")
        return

    if value <= 0:
        errors.append(f"{name} must be greater than 0")


def check_non_empty_string(name, value, errors):
    if not isinstance(value, str):
        errors.append(f"{name} must be a string")
        return

    if not value.strip():
        errors.append(f"{name} must not be empty")


def check_non_empty_list(name, value, errors):
    if not isinstance(value, list):
        errors.append(f"{name} must be a list")
        return

    if not value:
        errors.append(f"{name} must not be empty")


def validate_config():
    errors = []

    # Account settings
    check_positive_number("ACCOUNT_VALUE", ACCOUNT_VALUE, errors)
    check_positive_number("ACCOUNT_SIZE", ACCOUNT_SIZE, errors)
    check_ratio("RISK_PER_TRADE", RISK_PER_TRADE, errors)

    # Portfolio risk settings
    check_positive_integer("MAX_HOLDINGS", MAX_HOLDINGS, errors)
    check_ratio("MAX_SINGLE_POSITION_WEIGHT", MAX_SINGLE_POSITION_WEIGHT, errors)
    check_ratio("MAX_TOTAL_EXPOSURE", MAX_TOTAL_EXPOSURE, errors)
    check_ratio("CASH_RESERVE_RATIO", CASH_RESERVE_RATIO, errors)

    if MAX_SINGLE_POSITION_WEIGHT > MAX_TOTAL_EXPOSURE:
        errors.append("MAX_SINGLE_POSITION_WEIGHT must not exceed MAX_TOTAL_EXPOSURE")

    if MAX_TOTAL_EXPOSURE + CASH_RESERVE_RATIO > 1:
        errors.append("MAX_TOTAL_EXPOSURE + CASH_RESERVE_RATIO must not exceed 1")

    # Risk multipliers
    check_ratio("LOW_RISK_WEIGHT_MULTIPLIER", LOW_RISK_WEIGHT_MULTIPLIER, errors)
    check_ratio("MEDIUM_RISK_WEIGHT_MULTIPLIER", MEDIUM_RISK_WEIGHT_MULTIPLIER, errors)
    check_ratio("HIGH_RISK_WEIGHT_MULTIPLIER", HIGH_RISK_WEIGHT_MULTIPLIER, errors)
    check_ratio("UNKNOWN_RISK_WEIGHT_MULTIPLIER", UNKNOWN_RISK_WEIGHT_MULTIPLIER, errors)

    # Order review settings
    check_positive_integer("MAX_ORDER_COUNT", MAX_ORDER_COUNT, errors)
    check_positive_number("MAX_TOTAL_ORDER_VALUE", MAX_TOTAL_ORDER_VALUE, errors)
    check_positive_number("MAX_SINGLE_ORDER_VALUE", MAX_SINGLE_ORDER_VALUE, errors)

    if MAX_SINGLE_ORDER_VALUE > MAX_TOTAL_ORDER_VALUE:
        errors.append("MAX_SINGLE_ORDER_VALUE must not exceed MAX_TOTAL_ORDER_VALUE")

    check_non_empty_list("ALLOWED_ACTIONS", ALLOWED_ACTIONS, errors)
    check_non_empty_list("ALLOWED_ORDER_STATUS", ALLOWED_ORDER_STATUS, errors)
    check_non_empty_list("ALLOWED_REVIEW_STATUS", ALLOWED_REVIEW_STATUS, errors)
    check_non_empty_list(
        "ALLOWED_PORTFOLIO_REVIEW_FLAG",
        ALLOWED_PORTFOLIO_REVIEW_FLAG,
        errors,
    )

    if "BUY" not in ALLOWED_ACTIONS:
        errors.append("ALLOWED_ACTIONS must include BUY")

    if "DRAFT_ONLY" not in ALLOWED_ORDER_STATUS:
        errors.append("ALLOWED_ORDER_STATUS must include DRAFT_ONLY")

    for status in ["PASS", "REVIEW", "BLOCKED"]:
        if status not in ALLOWED_REVIEW_STATUS:
            errors.append(f"ALLOWED_REVIEW_STATUS must include {status}")

    # Directories
    check_non_empty_string("DATA_DIR", DATA_DIR, errors)
    check_non_empty_string("RESULTS_DIR", RESULTS_DIR, errors)
    check_non_empty_string("REPORTS_DIR", REPORTS_DIR, errors)
    check_non_empty_string("LOGS_DIR", LOGS_DIR, errors)

    # Output files
    output_paths = {
        "STOCK_RANK_OUTPUT": STOCK_RANK_OUTPUT,
        "TOP10_OUTPUT": TOP10_OUTPUT,
        "MODEL_PORTFOLIO_OUTPUT": MODEL_PORTFOLIO_OUTPUT,
        "POSITION_SIZING_OUTPUT": POSITION_SIZING_OUTPUT,
        "ORDER_DRAFT_OUTPUT": ORDER_DRAFT_OUTPUT,
        "ORDER_REVIEW_OUTPUT": ORDER_REVIEW_OUTPUT,
        "PORTFOLIO_ACTION_REPORT_OUTPUT": PORTFOLIO_ACTION_REPORT_OUTPUT,
        "SYSTEM_VERSION_OUTPUT": SYSTEM_VERSION_OUTPUT,
        "DAILY_DECISION_REPORT_PREFIX": DAILY_DECISION_REPORT_PREFIX,
    }

    for name, value in output_paths.items():
        check_non_empty_string(name, value, errors)

    # Project version
    check_non_empty_string("PROJECT_VERSION", PROJECT_VERSION, errors)

    if isinstance(PROJECT_VERSION, str) and not PROJECT_VERSION.startswith("v"):
        errors.append("PROJECT_VERSION should start with v")

    return errors


def print_config_validation():
    print("=" * 80)
    print("AI INVESTING CONFIG VALIDATION")
    print("=" * 80)

    errors = validate_config()

    print("\nAccount settings checked:")
    print(f"- ACCOUNT_VALUE: {ACCOUNT_VALUE}")
    print(f"- ACCOUNT_SIZE: {ACCOUNT_SIZE}")
    print(f"- RISK_PER_TRADE: {RISK_PER_TRADE}")

    print("\nPortfolio risk settings checked:")
    print(f"- MAX_HOLDINGS: {MAX_HOLDINGS}")
    print(f"- MAX_SINGLE_POSITION_WEIGHT: {MAX_SINGLE_POSITION_WEIGHT}")
    print(f"- MAX_TOTAL_EXPOSURE: {MAX_TOTAL_EXPOSURE}")
    print(f"- CASH_RESERVE_RATIO: {CASH_RESERVE_RATIO}")

    print("\nOrder review settings checked:")
    print(f"- MAX_ORDER_COUNT: {MAX_ORDER_COUNT}")
    print(f"- MAX_TOTAL_ORDER_VALUE: {MAX_TOTAL_ORDER_VALUE}")
    print(f"- MAX_SINGLE_ORDER_VALUE: {MAX_SINGLE_ORDER_VALUE}")
    print(f"- ALLOWED_ACTIONS: {ALLOWED_ACTIONS}")
    print(f"- ALLOWED_ORDER_STATUS: {ALLOWED_ORDER_STATUS}")
    print(f"- ALLOWED_REVIEW_STATUS: {ALLOWED_REVIEW_STATUS}")

    print("\nOutput paths checked:")
    for path_name in [
        DATA_DIR,
        RESULTS_DIR,
        REPORTS_DIR,
        LOGS_DIR,
        STOCK_RANK_OUTPUT,
        TOP10_OUTPUT,
        MODEL_PORTFOLIO_OUTPUT,
        POSITION_SIZING_OUTPUT,
        ORDER_DRAFT_OUTPUT,
        ORDER_REVIEW_OUTPUT,
        PORTFOLIO_ACTION_REPORT_OUTPUT,
        SYSTEM_VERSION_OUTPUT,
        DAILY_DECISION_REPORT_PREFIX,
    ]:
        print(f"- {path_name}")

    print(f"\nProject version checked: {PROJECT_VERSION}")

    if errors:
        print("\nCONFIG VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise ValueError("Config validation failed")

    print("\nCONFIG VALIDATION PASSED")
    print("AI_investing config settings are valid.")


if __name__ == "__main__":
    print_config_validation()