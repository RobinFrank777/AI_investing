from pathlib import Path

import pandas as pd


POSITION_SIZING_OUTPUT = "results/model_portfolio_sizing.csv"

REQUIRED_COLUMNS = [
    "Ticker",
    "BacktestScore",
    "RiskLevel",
    "RiskWeightMultiplier",
    "TargetWeight",
    "TargetWeightPercent",
    "LatestClose",
    "AccountValue",
    "TargetDollarAmount",
    "TargetShares",
    "EstimatedPositionValue",
    "PositionCashRemainder",
    "PortfolioRole",
]

NUMERIC_COLUMNS = [
    "BacktestScore",
    "RiskWeightMultiplier",
    "TargetWeight",
    "LatestClose",
    "AccountValue",
    "TargetDollarAmount",
    "TargetShares",
    "EstimatedPositionValue",
    "PositionCashRemainder",
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


def check_target_dollar_amount(df):
    errors = []

    required_columns = [
        "TargetWeight",
        "AccountValue",
        "TargetDollarAmount",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    expected_amount = (df["TargetWeight"] * df["AccountValue"]).round(2)
    actual_amount = df["TargetDollarAmount"].round(2)

    mismatched_rows = df[expected_amount != actual_amount]

    if not mismatched_rows.empty:
        errors.append(
            "TargetDollarAmount does not match TargetWeight * AccountValue"
        )

    return errors


def check_target_shares(df):
    errors = []

    required_columns = [
        "TargetDollarAmount",
        "LatestClose",
        "TargetShares",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    expected_shares = (
        df["TargetDollarAmount"] / df["LatestClose"]
    ).astype(int)

    actual_shares = df["TargetShares"].astype(int)

    mismatched_rows = df[expected_shares != actual_shares]

    if not mismatched_rows.empty:
        errors.append(
            "TargetShares does not match int(TargetDollarAmount / LatestClose)"
        )

    return errors


def check_estimated_position_value(df):
    errors = []

    required_columns = [
        "TargetShares",
        "LatestClose",
        "EstimatedPositionValue",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    expected_value = (
        df["TargetShares"] * df["LatestClose"]
    ).round(2)

    actual_value = df["EstimatedPositionValue"].round(2)

    mismatched_rows = df[expected_value != actual_value]

    if not mismatched_rows.empty:
        errors.append(
            "EstimatedPositionValue does not match TargetShares * LatestClose"
        )

    return errors


def check_position_cash_remainder(df):
    errors = []

    required_columns = [
        "TargetDollarAmount",
        "EstimatedPositionValue",
        "PositionCashRemainder",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    expected_remainder = (
        df["TargetDollarAmount"] - df["EstimatedPositionValue"]
    ).round(2)

    actual_remainder = df["PositionCashRemainder"].round(2)

    mismatched_rows = df[expected_remainder != actual_remainder]

    if not mismatched_rows.empty:
        errors.append(
            "PositionCashRemainder does not match TargetDollarAmount - EstimatedPositionValue"
        )

    return errors


def check_total_exposure(df):
    errors = []

    required_columns = [
        "EstimatedPositionValue",
        "AccountValue",
    ]

    for column in required_columns:
        if column not in df.columns:
            return errors

    account_value = df["AccountValue"].iloc[0]
    estimated_invested = df["EstimatedPositionValue"].sum()

    if estimated_invested > account_value:
        errors.append(
            "total EstimatedPositionValue exceeds AccountValue"
        )

    return errors


def validate_position_sizing_outputs():
    output_path = Path(POSITION_SIZING_OUTPUT)

    if not output_path.exists():
        raise FileNotFoundError(
            f"Missing position sizing output file: {POSITION_SIZING_OUTPUT}"
        )

    df = pd.read_csv(output_path)

    errors = []

    errors.extend(check_required_columns(df))
    errors.extend(check_numeric_columns(df))
    errors.extend(check_target_dollar_amount(df))
    errors.extend(check_target_shares(df))
    errors.extend(check_estimated_position_value(df))
    errors.extend(check_position_cash_remainder(df))
    errors.extend(check_total_exposure(df))

    print("=" * 70)
    print("POSITION SIZING OUTPUT VALIDATION")
    print("=" * 70)

    print(f"Position sizing file : {POSITION_SIZING_OUTPUT}")
    print(f"Rows                 : {len(df)}")

    print("\nNumeric columns checked:")
    for column in NUMERIC_COLUMNS:
        print(f"- {column}")

    print("\nFormulas checked:")
    print("- TargetDollarAmount = TargetWeight * AccountValue")
    print("- TargetShares = int(TargetDollarAmount / LatestClose)")
    print("- EstimatedPositionValue = TargetShares * LatestClose")
    print("- PositionCashRemainder = TargetDollarAmount - EstimatedPositionValue")

    print("\nRisk rule checked:")
    print("- total EstimatedPositionValue <= AccountValue")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")

        raise RuntimeError("Position sizing output validation failed.")

    print("\nVALIDATION PASSED")
    print("Position sizing output is valid.")


if __name__ == "__main__":
    validate_position_sizing_outputs()