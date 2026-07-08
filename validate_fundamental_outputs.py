from pathlib import Path

import pandas as pd

from config import (
    FUNDAMENTAL_SCORE_OUTPUT as CONFIG_FUNDAMENTAL_SCORE_OUTPUT,
)


FUNDAMENTAL_SCORE_OUTPUT = Path(CONFIG_FUNDAMENTAL_SCORE_OUTPUT)


REQUIRED_COLUMNS = [
    "Ticker",
    "FundamentalScore",
    "FundamentalRating",
    "RevenueGrowth",
    "EPSGrowth",
    "GrossMargin",
    "OperatingMargin",
    "ROE",
    "FreeCashFlowMargin",
    "DebtToEquity",
    "PE",
    "PS",
]


NUMERIC_COLUMNS = [
    "FundamentalScore",
    "RevenueGrowth",
    "EPSGrowth",
    "GrossMargin",
    "OperatingMargin",
    "ROE",
    "FreeCashFlowMargin",
    "DebtToEquity",
    "PE",
    "PS",
]


ALLOWED_RATINGS = [
    "STRONG",
    "GOOD",
    "NEUTRAL",
    "WEAK",
]


def validate_fundamental_outputs():
    if not FUNDAMENTAL_SCORE_OUTPUT.exists():
        raise FileNotFoundError(
            f"Missing fundamental score output: {FUNDAMENTAL_SCORE_OUTPUT}"
        )

    df = pd.read_csv(FUNDAMENTAL_SCORE_OUTPUT)

    if df.empty:
        raise ValueError("Fundamental score output is empty")

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[col].isna().any():
            raise ValueError(f"Column contains non-numeric or missing values: {col}")

    if not df["FundamentalScore"].between(0, 100).all():
        raise ValueError("FundamentalScore must be between 0 and 100")

    invalid_ratings = df[~df["FundamentalRating"].isin(ALLOWED_RATINGS)]

    if not invalid_ratings.empty:
        raise ValueError(
            f"Invalid FundamentalRating values found: "
            f"{invalid_ratings['FundamentalRating'].unique().tolist()}"
        )

    if df["Ticker"].duplicated().any():
        duplicated_tickers = df[df["Ticker"].duplicated()]["Ticker"].tolist()
        raise ValueError(f"Duplicated tickers found: {duplicated_tickers}")

    print("=" * 80)
    print("AI INVESTING FUNDAMENTAL OUTPUT VALIDATION")
    print("=" * 80)
    print("")
    print("VALIDATION PASSED")
    print(f"Fundamental score output is valid: {FUNDAMENTAL_SCORE_OUTPUT}")


if __name__ == "__main__":
    validate_fundamental_outputs()