import pandas as pd

from config import (
    BACKTEST_ALL_TRADES_20D_OUTPUT_PATH,
    BACKTEST_QUALIFIED_20D_OUTPUT_PATH,
    BACKTEST_SUMMARY_20D_OUTPUT_PATH,
)


SUMMARY_OUTPUT = BACKTEST_SUMMARY_20D_OUTPUT_PATH
QUALIFIED_OUTPUT = BACKTEST_QUALIFIED_20D_OUTPUT_PATH
ALL_TRADES_OUTPUT = BACKTEST_ALL_TRADES_20D_OUTPUT_PATH

NUMERIC_COLUMNS = [
    "AverageReturn",
    "WinRate",
    "TotalReturn",
    "MaxDrawdown",
    "SharpeRatio",
    "BacktestScore",
]


def check_numeric_columns(df, file_name):
    errors = []

    for column in NUMERIC_COLUMNS:
        if column not in df.columns:
            errors.append(f"{file_name}: missing column {column}")
            continue

        if df[column].astype(str).str.contains("%", regex=False).any():
            errors.append(f"{file_name}: column {column} contains percent strings")

        if not pd.api.types.is_numeric_dtype(df[column]):
            errors.append(f"{file_name}: column {column} is not numeric")

    return errors


def validate_backtest_outputs():
    summary_df = pd.read_csv(SUMMARY_OUTPUT)
    qualified_df = pd.read_csv(QUALIFIED_OUTPUT)
    all_trades_df = pd.read_csv(ALL_TRADES_OUTPUT)

    errors = []

    if summary_df.empty:
        errors.append(f"{SUMMARY_OUTPUT}: output is empty")

    if qualified_df.empty:
        errors.append(f"{QUALIFIED_OUTPUT}: output is empty")

    if all_trades_df.empty:
        errors.append(f"{ALL_TRADES_OUTPUT}: output is empty")

    errors.extend(
        check_numeric_columns(
            summary_df,
            SUMMARY_OUTPUT,
        )
    )

    errors.extend(
        check_numeric_columns(
            qualified_df,
            QUALIFIED_OUTPUT,
        )
    )

    print("=" * 70)
    print("BACKTEST OUTPUT VALIDATION")
    print("=" * 70)
    print(f"Summary file    : {SUMMARY_OUTPUT}")
    print(f"Qualified file  : {QUALIFIED_OUTPUT}")
    print(f"All trades file : {ALL_TRADES_OUTPUT}")

    print("\nSummary rows    :", len(summary_df))
    print("Qualified rows  :", len(qualified_df))
    print("All trade rows  :", len(all_trades_df))

    print("\nNumeric columns checked:")
    for column in NUMERIC_COLUMNS:
        print(f"- {column}")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")

        raise RuntimeError("Backtest output validation failed.")

    print("\nVALIDATION PASSED")
    print("Backtest output CSV files keep numeric values.")


if __name__ == "__main__":
    validate_backtest_outputs()
