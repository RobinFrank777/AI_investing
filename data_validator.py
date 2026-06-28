from pathlib import Path

import pandas as pd
from watchlist import load_watchlist

DATA_DIR = Path("data")

REQUIRED_COLUMNS = [
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]

MIN_HISTORY_ROWS = 252


def validate_stock_file(ticker):
    file_path = DATA_DIR / f"{ticker}.csv"

    errors = []
    warnings = []

    # 1. Check whether the CSV file exists.
    if not file_path.exists():
        errors.append(f"File not found: {file_path}")

        return {
            "Ticker": ticker,
            "IsValid": False,
            "LatestDate": None,
            "Errors": errors,
            "Warnings": warnings,
        }

    # 2. Try to read the CSV file.
    try:
        df = pd.read_csv(file_path)

    except Exception as error:
        errors.append(f"Unable to read CSV: {error}")

        return {
            "Ticker": ticker,
            "IsValid": False,
            "LatestDate": None,
            "Errors": errors,
            "Warnings": warnings,
        }

    # 3. Check whether the DataFrame is empty.
    if df.empty:
        errors.append("CSV file contains no data.")

        return {
            "Ticker": ticker,
            "IsValid": False,
            "LatestDate": None,
            "Errors": errors,
            "Warnings": warnings,
        }

    # 4. Check required columns.
    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        errors.append(
            f"Missing required columns: {missing_columns}"
        )

        return {
            "Ticker": ticker,
            "IsValid": False,
            "LatestDate": None,
            "Errors": errors,
            "Warnings": warnings,
        }

    # 5. Convert Date values and find invalid dates.
    parsed_dates = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    invalid_date_count = int(parsed_dates.isna().sum())

    if invalid_date_count > 0:
        errors.append(
            f"Invalid Date values: {invalid_date_count}"
        )

    # 6. Check duplicate dates.
    duplicate_date_count = int(
        parsed_dates.dropna().duplicated().sum()
    )

    if duplicate_date_count > 0:
        warnings.append(
            f"Duplicate dates: {duplicate_date_count}"
        )

    # 7. Check whether enough history is available.
    row_count = len(df)

    if row_count < MIN_HISTORY_ROWS:
        errors.append(
            f"Insufficient history: {row_count} rows; "
            f"at least {MIN_HISTORY_ROWS} required."
        )

    # 8. Check numeric market-data columns.
    numeric_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    numeric_data = df[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    invalid_numeric_count = int(
        numeric_data.isna().sum().sum()
    )

    if invalid_numeric_count > 0:
        errors.append(
            f"Missing or invalid numeric values: "
            f"{invalid_numeric_count}"
        )

    # 9. Find the latest valid market date.
    latest_date = None

    if parsed_dates.notna().any():
        latest_date = (
            parsed_dates.max().strftime("%Y-%m-%d")
        )

    return {
        "Ticker": ticker,
        "IsValid": len(errors) == 0,
        "LatestDate": latest_date,
        "RowCount": row_count,
        "Errors": errors,
        "Warnings": warnings,
    }

def validate_watchlist():
    tickers = load_watchlist()

    results = []

    for ticker in tickers:
        result = validate_stock_file(ticker)
        results.append(result)

    latest_dates = [
        result["LatestDate"]
        for result in results
        if result["LatestDate"] is not None
    ]

    if latest_dates:
        universe_latest_date = max(latest_dates)
    else:
        universe_latest_date = None

    for result in results:
        latest_date = result["LatestDate"]

        if (
            universe_latest_date is not None
            and latest_date is not None
            and latest_date < universe_latest_date
        ):
            result["Warnings"].append(
                f"Latest date {latest_date} is behind "
                f"universe latest date {universe_latest_date}."
            )

    return results, universe_latest_date

def print_validation_summary(results, universe_latest_date):
    print("\n" + "=" * 70)
    print("DATA VALIDATION SUMMARY")
    print("=" * 70)

    print(
        f"{'Universe Latest Date':<24}: "
        f"{universe_latest_date}"
    )

    print(f"{'Stocks Checked':<24}: {len(results)}")
    print()

    for result in results:
        if not result["IsValid"]:
            status = "FAIL"
        elif result["Warnings"]:
            status = "WARNING"
        else:
            status = "PASS"

        print(
            f"{result['Ticker']:<8}"
            f"{status:<10}"
            f"Latest Date: {str(result['LatestDate']):<12}"
            f"Rows: {result.get('RowCount', 0)}"
        )

        for error in result["Errors"]:
            print(f"    ERROR: {error}")

        for warning in result["Warnings"]:
            print(f"    WARNING: {warning}")

    invalid_count = sum(
        not result["IsValid"]
        for result in results
    )

    warning_count = sum(
        bool(result["Warnings"])
        for result in results
    )

    print("\n" + "-" * 70)
    print(f"{'Invalid Stocks':<24}: {invalid_count}")
    print(f"{'Stocks with Warnings':<24}: {warning_count}")
    print("=" * 70)

if __name__ == "__main__":
    validation_results, universe_latest_date = (
        validate_watchlist()
    )

    print_validation_summary(
        validation_results,
        universe_latest_date,
    )