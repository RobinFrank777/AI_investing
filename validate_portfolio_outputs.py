import pandas as pd

from portfolio_risk import (
    MODEL_PORTFOLIO_OUTPUT,
    MAX_POSITION_WEIGHT,
    MAX_TOTAL_EXPOSURE,
    MAX_HOLDINGS,
)


REQUIRED_COLUMNS = [
    "Ticker",
    "BacktestScore",
    "AverageReturn",
    "WinRate",
    "MaxDrawdown",
    "SharpeRatio",
    "RiskLevel",
    "RiskWeightMultiplier",
    "TargetWeight",
    "TargetWeightPercent",
    "PortfolioRole",
]


NUMERIC_COLUMNS = [
    "BacktestScore",
    "AverageReturn",
    "WinRate",
    "MaxDrawdown",
    "SharpeRatio",
    "RiskWeightMultiplier",
    "TargetWeight",
]

ALLOWED_RISK_LEVELS = [
    "Low",
    "Medium",
    "High",
    "Unknown",
]

def validate_portfolio_outputs():
    errors = []

    df = pd.read_csv(MODEL_PORTFOLIO_OUTPUT)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        errors.append(f"Missing columns: {missing_columns}")

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            converted = pd.to_numeric(df[column], errors="coerce")

            if converted.isna().any():
                errors.append(f"Column has non-numeric values: {column}")

            df[column] = converted

    if "Ticker" in df.columns:
        duplicate_tickers = df[df["Ticker"].duplicated()]["Ticker"].tolist()

        if duplicate_tickers:
            errors.append(f"Duplicate tickers: {duplicate_tickers}")

    if "RiskLevel" in df.columns:
        invalid_risk_levels = sorted(
            set(df["RiskLevel"].dropna()) - set(ALLOWED_RISK_LEVELS)
        )

        if invalid_risk_levels:
            errors.append(f"Invalid risk levels: {invalid_risk_levels}")

    if len(df) > MAX_HOLDINGS:
        errors.append(
            f"Too many holdings: {len(df)}; max allowed: {MAX_HOLDINGS}"
        )

    if "TargetWeight" in df.columns:
        max_weight = df["TargetWeight"].max()
        total_weight = df["TargetWeight"].sum()

        if max_weight > MAX_POSITION_WEIGHT:
            errors.append(
                f"Single position weight too high: {max_weight:.2%}; "
                f"max allowed: {MAX_POSITION_WEIGHT:.2%}"
            )

        if total_weight > MAX_TOTAL_EXPOSURE:
            errors.append(
                f"Total exposure too high: {total_weight:.2%}; "
                f"max allowed: {MAX_TOTAL_EXPOSURE:.2%}"
            )

    print("=" * 70)
    print("PORTFOLIO OUTPUT VALIDATION")
    print("=" * 70)

    print(f"Portfolio file : {MODEL_PORTFOLIO_OUTPUT}")
    print(f"Rows           : {len(df)}")

    print("\nNumeric columns checked:")
    for column in NUMERIC_COLUMNS:
        print(f"- {column}")

    print("\nRisk rules checked:")
    print(f"- max holdings         : {MAX_HOLDINGS}")
    print(f"- max position weight  : {MAX_POSITION_WEIGHT:.2%}")
    print(f"- max total exposure   : {MAX_TOTAL_EXPOSURE:.2%}")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")

        raise RuntimeError("Portfolio output validation failed.")

    print("\nVALIDATION PASSED")
    print("Model portfolio output is valid.")


if __name__ == "__main__":
    validate_portfolio_outputs()