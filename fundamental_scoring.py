from pathlib import Path

import pandas as pd

from config import (
    FUNDAMENTAL_INPUT as CONFIG_FUNDAMENTAL_INPUT,
    FUNDAMENTAL_SCORE_OUTPUT as CONFIG_FUNDAMENTAL_SCORE_OUTPUT,
)


FUNDAMENTAL_INPUT = Path(CONFIG_FUNDAMENTAL_INPUT)
FUNDAMENTAL_SCORE_OUTPUT = Path(CONFIG_FUNDAMENTAL_SCORE_OUTPUT)


REQUIRED_COLUMNS = [
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
]


NUMERIC_COLUMNS = [
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


def score_positive(value, low, high):
    """
    Higher value is better.
    Example: revenue growth, ROE, free cash flow margin.
    """
    if pd.isna(value):
        return 0

    score = (value - low) / (high - low) * 100
    return max(0, min(100, score))


def score_negative(value, low, high):
    """
    Lower value is better.
    Example: debt-to-equity, PE, PS.
    """
    if pd.isna(value):
        return 0

    score = (high - value) / (high - low) * 100
    return max(0, min(100, score))


def load_fundamental_data():
    if not FUNDAMENTAL_INPUT.exists():
        raise FileNotFoundError(f"Missing input file: {FUNDAMENTAL_INPUT}")

    df = pd.read_csv(FUNDAMENTAL_INPUT)

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def assign_fundamental_rating(score):
    if score >= 75:
        return "STRONG"
    if score >= 60:
        return "GOOD"
    if score >= 45:
        return "NEUTRAL"
    return "WEAK"


def calculate_fundamental_score(df):
    result_df = df.copy()

    result_df["RevenueGrowthScore"] = result_df["RevenueGrowth"].apply(
        lambda value: score_positive(value, 0.00, 0.40)
    )
    result_df["EPSGrowthScore"] = result_df["EPSGrowth"].apply(
        lambda value: score_positive(value, 0.00, 0.40)
    )
    result_df["GrossMarginScore"] = result_df["GrossMargin"].apply(
        lambda value: score_positive(value, 0.20, 0.80)
    )
    result_df["OperatingMarginScore"] = result_df["OperatingMargin"].apply(
        lambda value: score_positive(value, 0.00, 0.40)
    )
    result_df["ROEScore"] = result_df["ROE"].apply(
        lambda value: score_positive(value, 0.00, 0.40)
    )
    result_df["FreeCashFlowMarginScore"] = result_df["FreeCashFlowMargin"].apply(
        lambda value: score_positive(value, 0.00, 0.30)
    )
    result_df["DebtToEquityScore"] = result_df["DebtToEquity"].apply(
        lambda value: score_negative(value, 0.00, 2.00)
    )
    result_df["PEScore"] = result_df["PE"].apply(
        lambda value: score_negative(value, 10.00, 60.00)
    )
    result_df["PSScore"] = result_df["PS"].apply(
        lambda value: score_negative(value, 2.00, 30.00)
    )

    result_df["FundamentalScore"] = (
        result_df["RevenueGrowthScore"] * 0.15
        + result_df["EPSGrowthScore"] * 0.15
        + result_df["GrossMarginScore"] * 0.10
        + result_df["OperatingMarginScore"] * 0.10
        + result_df["ROEScore"] * 0.15
        + result_df["FreeCashFlowMarginScore"] * 0.15
        + result_df["DebtToEquityScore"] * 0.10
        + result_df["PEScore"] * 0.05
        + result_df["PSScore"] * 0.05
    ).round(2)

    result_df["FundamentalRating"] = result_df["FundamentalScore"].apply(
        assign_fundamental_rating
    )

    output_columns = [
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

    return result_df[output_columns].sort_values(
        by="FundamentalScore",
        ascending=False,
    )


def print_fundamental_score():
    df = load_fundamental_data()
    result_df = calculate_fundamental_score(df)

    FUNDAMENTAL_SCORE_OUTPUT.parent.mkdir(exist_ok=True)
    result_df.to_csv(FUNDAMENTAL_SCORE_OUTPUT, index=False)

    print("=" * 80)
    print("AI INVESTING FUNDAMENTAL SCORING")
    print("=" * 80)
    print(result_df.to_string(index=False))
    print("")
    print(f"Saved Fundamental Score To : {FUNDAMENTAL_SCORE_OUTPUT}")


if __name__ == "__main__":
    print_fundamental_score()