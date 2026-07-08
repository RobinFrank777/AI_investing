from pathlib import Path

import pandas as pd

from config import (
    COMBINED_SCORE_OUTPUT,
    BACKTEST_SCORE_WEIGHT,
    FUNDAMENTAL_SCORE_WEIGHT,
)


REQUIRED_COLUMNS = [
    "Ticker",
    "BacktestScore",
    "FundamentalScore",
    "CombinedScore",
    "FundamentalRating",
]

NUMERIC_COLUMNS = [
    "BacktestScore",
    "FundamentalScore",
    "CombinedScore",
]

ALLOWED_FUNDAMENTAL_RATINGS = [
    "STRONG",
    "GOOD",
    "NEUTRAL",
    "WEAK",
    "MISSING",
]


def load_combined_score_output():
    output_path = Path(COMBINED_SCORE_OUTPUT)

    if not output_path.exists():
        raise FileNotFoundError(
            f"Combined score output file not found: {COMBINED_SCORE_OUTPUT}"
        )

    return pd.read_csv(output_path)


def validate_required_columns(df):
    missing_columns = []

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            missing_columns.append(col)

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")


def validate_numeric_columns(df):
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[col].isna().any():
            raise ValueError(f"Column contains non-numeric or missing values: {col}")


def validate_score_ranges(df):
    if (df["BacktestScore"] < 0).any():
        raise ValueError("BacktestScore contains negative values")

    if not df["FundamentalScore"].between(0, 100).all():
        raise ValueError("FundamentalScore must be between 0 and 100")

    if (df["CombinedScore"] < 0).any():
        raise ValueError("CombinedScore contains negative values")


def validate_fundamental_ratings(df):
    invalid_ratings = df[
        ~df["FundamentalRating"].isin(ALLOWED_FUNDAMENTAL_RATINGS)
    ]

    if not invalid_ratings.empty:
        raise ValueError(
            "Invalid FundamentalRating values found: "
            f"{invalid_ratings['FundamentalRating'].unique().tolist()}"
        )


def validate_duplicate_tickers(df):
    if df["Ticker"].duplicated().any():
        duplicated_tickers = df[df["Ticker"].duplicated()]["Ticker"].tolist()
        raise ValueError(f"Duplicated tickers found: {duplicated_tickers}")


def validate_combined_score_formula(df):
    expected_score = (
        df["BacktestScore"] * BACKTEST_SCORE_WEIGHT
        + df["FundamentalScore"] * FUNDAMENTAL_SCORE_WEIGHT
    ).round(2)

    actual_score = df["CombinedScore"].round(2)

    mismatches = df[actual_score != expected_score]

    if not mismatches.empty:
        raise ValueError(
            "CombinedScore formula mismatch found for tickers: "
            f"{mismatches['Ticker'].tolist()}"
        )


def validate_combined_outputs():
    df = load_combined_score_output()

    validate_required_columns(df)
    validate_numeric_columns(df)
    validate_score_ranges(df)
    validate_fundamental_ratings(df)
    validate_duplicate_tickers(df)
    validate_combined_score_formula(df)

    print("=" * 80)
    print("AI INVESTING COMBINED SCORE OUTPUT VALIDATION")
    print("=" * 80)
    print()
    print("VALIDATION PASSED")
    print(f"Combined score output is valid: {COMBINED_SCORE_OUTPUT}")


if __name__ == "__main__":
    validate_combined_outputs()