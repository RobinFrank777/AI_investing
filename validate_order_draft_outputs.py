from pathlib import Path

import pandas as pd


ORDER_DRAFT_OUTPUT = Path("results/order_draft.csv")

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


def check_action_values(df):
    errors = []

    if "Action" not in df.columns:
        return errors

    invalid_rows = df[df["Action"] != "BUY"]

    if not invalid_rows.empty:
        errors.append("Action must be BUY for all draft orders")

    return errors


def check_order_status_values(df):
    errors = []

    if "OrderStatus" not in df.columns:
        return errors

    invalid_rows = df[df["OrderStatus"] != "DRAFT_ONLY"]

    if not invalid_rows.empty:
        errors.append("OrderStatus must be DRAFT_ONLY for all draft orders")

    return errors


def check_target_shares(df):
    errors = []

    if "TargetShares" not in df.columns:
        return errors

    if (df["TargetShares"] <= 0).any():
        errors.append("TargetShares must be greater than zero")

    if (df["TargetShares"] % 1 != 0).any():
        errors.append("TargetShares must be whole shares")

    return errors


def check_estimated_order_value(df):
    errors = []

    required_columns = [
        "TargetShares",
        "LatestClose",
        "EstimatedOrderValue",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    expected_value = (
        df["TargetShares"] * df["LatestClose"]
    ).round(2)

    actual_value = df["EstimatedOrderValue"].round(2)

    mismatched_rows = df[expected_value != actual_value]

    if not mismatched_rows.empty:
        errors.append(
            "EstimatedOrderValue does not match TargetShares * LatestClose"
        )

    return errors


def check_order_value_not_above_target(df):
    errors = []

    required_columns = [
        "EstimatedOrderValue",
        "TargetDollarAmount",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    invalid_rows = df[
        df["EstimatedOrderValue"].round(2)
        > df["TargetDollarAmount"].round(2)
    ]

    if not invalid_rows.empty:
        errors.append(
            "EstimatedOrderValue exceeds TargetDollarAmount"
        )

    return errors


def validate_order_draft_outputs():
    if not ORDER_DRAFT_OUTPUT.exists():
        raise FileNotFoundError(
            f"Missing order draft output file: {ORDER_DRAFT_OUTPUT}"
        )

    df = pd.read_csv(ORDER_DRAFT_OUTPUT)

    errors = []

    errors.extend(check_required_columns(df))
    errors.extend(check_numeric_columns(df))
    errors.extend(check_action_values(df))
    errors.extend(check_order_status_values(df))
    errors.extend(check_target_shares(df))
    errors.extend(check_estimated_order_value(df))
    errors.extend(check_order_value_not_above_target(df))

    print("=" * 70)
    print("ORDER DRAFT OUTPUT VALIDATION")
    print("=" * 70)

    print(f"Order draft file : {ORDER_DRAFT_OUTPUT}")
    print(f"Rows             : {len(df)}")

    print("\nNumeric columns checked:")
    for column in NUMERIC_COLUMNS:
        print(f"- {column}")

    print("\nRules checked:")
    print("- Action = BUY")
    print("- OrderStatus = DRAFT_ONLY")
    print("- TargetShares > 0")
    print("- TargetShares are whole shares")
    print("- EstimatedOrderValue = TargetShares * LatestClose")
    print("- EstimatedOrderValue <= TargetDollarAmount")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")

        raise RuntimeError("Order draft output validation failed.")

    print("\nVALIDATION PASSED")
    print("Order draft output is valid.")


if __name__ == "__main__":
    validate_order_draft_outputs()