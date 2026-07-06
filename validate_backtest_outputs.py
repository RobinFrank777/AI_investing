import pandas as pd


SUMMARY_OUTPUT = "results/backtest_summary_20d.csv"
QUALIFIED_OUTPUT = "results/backtest_qualified_20d.csv"

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

    errors = []

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

    print(f"Summary file   : {SUMMARY_OUTPUT}")
    print(f"Qualified file : {QUALIFIED_OUTPUT}")

    print("\nSummary rows   :", len(summary_df))
    print("Qualified rows :", len(qualified_df))

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