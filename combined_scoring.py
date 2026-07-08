from pathlib import Path

import pandas as pd

from config import (
    MODEL_PORTFOLIO_OUTPUT,
    FUNDAMENTAL_SCORE_OUTPUT,
    COMBINED_SCORE_OUTPUT,
    BACKTEST_SCORE_WEIGHT,
    FUNDAMENTAL_SCORE_WEIGHT,
)


REQUIRED_MODEL_COLUMNS = [
    "Ticker",
    "BacktestScore",
]

REQUIRED_FUNDAMENTAL_COLUMNS = [
    "Ticker",
    "FundamentalScore",
    "FundamentalRating",
]


def load_csv(path):
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Required input file not found: {file_path}")

    return pd.read_csv(file_path)


def check_required_columns(df, required_columns, file_name):
    missing_columns = []

    for col in required_columns:
        if col not in df.columns:
            missing_columns.append(col)

    if missing_columns:
        raise ValueError(
            f"{file_name} is missing required columns: {missing_columns}"
        )


def calculate_combined_score(model_df, fundamental_df):
    check_required_columns(
        model_df,
        REQUIRED_MODEL_COLUMNS,
        MODEL_PORTFOLIO_OUTPUT,
    )

    check_required_columns(
        fundamental_df,
        REQUIRED_FUNDAMENTAL_COLUMNS,
        FUNDAMENTAL_SCORE_OUTPUT,
    )

    merged_df = model_df.merge(
        fundamental_df[
            [
                "Ticker",
                "FundamentalScore",
                "FundamentalRating",
            ]
        ],
        on="Ticker",
        how="left",
    )

    merged_df["BacktestScore"] = pd.to_numeric(
        merged_df["BacktestScore"],
        errors="coerce",
    )

    merged_df["FundamentalScore"] = pd.to_numeric(
        merged_df["FundamentalScore"],
        errors="coerce",
    )

    merged_df["FundamentalScore"] = merged_df["FundamentalScore"].fillna(0)
    merged_df["FundamentalRating"] = merged_df["FundamentalRating"].fillna("MISSING")

    merged_df["CombinedScore"] = (
        merged_df["BacktestScore"] * BACKTEST_SCORE_WEIGHT
        + merged_df["FundamentalScore"] * FUNDAMENTAL_SCORE_WEIGHT
    )

    merged_df["CombinedScore"] = merged_df["CombinedScore"].round(2)

    output_columns = [
        "Ticker",
        "BacktestScore",
        "FundamentalScore",
        "CombinedScore",
        "FundamentalRating",
    ]

    remaining_columns = [
        col for col in merged_df.columns if col not in output_columns
    ]

    result_df = merged_df[output_columns + remaining_columns].sort_values(
        by="CombinedScore",
        ascending=False,
    )

    return result_df


def print_combined_score():
    model_df = load_csv(MODEL_PORTFOLIO_OUTPUT)
    fundamental_df = load_csv(FUNDAMENTAL_SCORE_OUTPUT)

    result_df = calculate_combined_score(model_df, fundamental_df)

    output_path = Path(COMBINED_SCORE_OUTPUT)
    output_path.parent.mkdir(exist_ok=True)
    result_df.to_csv(output_path, index=False)

    print("=" * 80)
    print("AI INVESTING COMBINED SCORING")
    print("=" * 80)
    print(
        result_df[
            [
                "Ticker",
                "BacktestScore",
                "FundamentalScore",
                "CombinedScore",
                "FundamentalRating",
            ]
        ].to_string(index=False)
    )
    print()
    print(f"Saved Combined Score To : {COMBINED_SCORE_OUTPUT}")


if __name__ == "__main__":
    print_combined_score()