from pathlib import Path

import pandas as pd


ORDER_REVIEW_OUTPUT = Path("results/order_review.csv")

ALLOWED_REVIEW_STATUS = ["PASS", "REVIEW", "BLOCKED"]
ALLOWED_PORTFOLIO_REVIEW_FLAG = ["PASS", "REVIEW"]

MAX_ORDER_COUNT = 10
MAX_TOTAL_ORDER_VALUE = 80_000
MAX_SINGLE_ORDER_VALUE = 10_000

REQUIRED_COLUMNS = [
    "Ticker",
    "Action",
    "TargetShares",
    "LatestClose",
    "EstimatedOrderValue",
    "TargetDollarAmount",
    "PositionCashRemainder",
    "RiskLevel",
    "RiskWeightMultiplier",
    "BacktestScore",
    "PortfolioRole",
    "OrderStatus",
    "ReviewStatus",
    "ReviewReason",
    "PortfolioReviewFlag",
    "PortfolioReviewReason",
]

NUMERIC_COLUMNS = [
    "TargetShares",
    "LatestClose",
    "EstimatedOrderValue",
    "TargetDollarAmount",
    "PositionCashRemainder",
    "RiskWeightMultiplier",
    "BacktestScore",
]


def check_required_columns(df):
    errors = []

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            errors.append(f"missing required column: {column}")

    return errors


def check_numeric_columns(df):
    errors = []

    for column in NUMERIC_COLUMNS:
        if column not in df.columns:
            continue

        if df[column].astype(str).str.contains("%", regex=False).any():
            errors.append(f"column {column} contains percent strings")

        if not pd.api.types.is_numeric_dtype(df[column]):
            errors.append(f"column {column} is not numeric")

    return errors


def check_review_status_values(df):
    errors = []

    if "ReviewStatus" not in df.columns:
        return errors

    invalid_rows = df[
        ~df["ReviewStatus"].isin(ALLOWED_REVIEW_STATUS)
    ]

    if not invalid_rows.empty:
        errors.append("ReviewStatus contains invalid values")

    return errors


def check_portfolio_review_flag_values(df):
    errors = []

    if "PortfolioReviewFlag" not in df.columns:
        return errors

    invalid_rows = df[
        ~df["PortfolioReviewFlag"].isin(ALLOWED_PORTFOLIO_REVIEW_FLAG)
    ]

    if not invalid_rows.empty:
        errors.append("PortfolioReviewFlag contains invalid values")

    return errors


def check_block_rules(df):
    errors = []

    required_columns = [
        "Action",
        "OrderStatus",
        "TargetShares",
        "EstimatedOrderValue",
        "ReviewStatus",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    blocked_condition = (
        (df["Action"] != "BUY")
        | (df["OrderStatus"] != "DRAFT_ONLY")
        | (df["TargetShares"] <= 0)
        | (df["EstimatedOrderValue"] <= 0)
    )

    invalid_rows = df[
        blocked_condition
        & (df["ReviewStatus"] != "BLOCKED")
    ]

    if not invalid_rows.empty:
        errors.append(
            "rows with hard rule violations must be BLOCKED"
        )

    return errors


def check_review_rules(df):
    errors = []

    required_columns = [
        "EstimatedOrderValue",
        "RiskLevel",
        "ReviewStatus",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    review_condition = (
        (df["EstimatedOrderValue"] > MAX_SINGLE_ORDER_VALUE)
        | (df["RiskLevel"] == "High")
    )

    invalid_rows = df[
        review_condition
        & (df["ReviewStatus"] == "PASS")
    ]

    if not invalid_rows.empty:
        errors.append(
            "high-risk or oversized orders must not be PASS"
        )

    return errors


def check_portfolio_level_rules(df):
    errors = []

    required_columns = [
        "EstimatedOrderValue",
        "PortfolioReviewFlag",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    total_order_value = df["EstimatedOrderValue"].sum()
    order_count = len(df)

    portfolio_review_required = (
        order_count > MAX_ORDER_COUNT
        or total_order_value > MAX_TOTAL_ORDER_VALUE
    )

    portfolio_flag = df["PortfolioReviewFlag"].iloc[0]

    if portfolio_review_required and portfolio_flag != "REVIEW":
        errors.append(
            "portfolio level review required but PortfolioReviewFlag is not REVIEW"
        )

    if not portfolio_review_required and portfolio_flag != "PASS":
        errors.append(
            "portfolio level checks passed but PortfolioReviewFlag is not PASS"
        )

    return errors


def validate_order_review_outputs():
    if not ORDER_REVIEW_OUTPUT.exists():
        raise FileNotFoundError(
            f"Missing order review output file: {ORDER_REVIEW_OUTPUT}"
        )

    df = pd.read_csv(ORDER_REVIEW_OUTPUT)

    errors = []

    errors.extend(check_required_columns(df))
    errors.extend(check_numeric_columns(df))
    errors.extend(check_review_status_values(df))
    errors.extend(check_portfolio_review_flag_values(df))
    errors.extend(check_block_rules(df))
    errors.extend(check_review_rules(df))
    errors.extend(check_portfolio_level_rules(df))

    print("=" * 70)
    print("ORDER REVIEW OUTPUT VALIDATION")
    print("=" * 70)

    print(f"Order review file : {ORDER_REVIEW_OUTPUT}")
    print(f"Rows              : {len(df)}")

    print("\nNumeric columns checked:")
    for column in NUMERIC_COLUMNS:
        print(f"- {column}")

    print("\nRules checked:")
    print("- required columns exist")
    print("- numeric columns stay numeric")
    print("- ReviewStatus is PASS / REVIEW / BLOCKED")
    print("- PortfolioReviewFlag is PASS / REVIEW")
    print("- hard rule violations become BLOCKED")
    print("- High risk or oversized orders are not PASS")
    print("- portfolio level review flag is correct")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")

        raise RuntimeError("Order review output validation failed.")

    print("\nVALIDATION PASSED")
    print("Order review output is valid.")


if __name__ == "__main__":
    validate_order_review_outputs()