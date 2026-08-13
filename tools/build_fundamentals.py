import sys
from pathlib import Path

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import DATA_DIR_PATH, display_path
from universe_loader import get_primary_tickers


OUTPUT_PATH = DATA_DIR_PATH / "fundamentals.preview.csv"

OUTPUT_COLUMNS = [
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


def divide_or_blank(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None

    return numerator / denominator


def debt_to_equity_ratio(value):
    if value is None:
        return None

    return value / 100


def build_fundamental_row(ticker):
    info = yf.Ticker(ticker).get_info()

    free_cashflow = info.get("freeCashflow")
    total_revenue = info.get("totalRevenue")

    return {
        "Ticker": ticker,
        "RevenueGrowth": info.get("revenueGrowth"),
        "EPSGrowth": info.get("earningsGrowth"),
        "GrossMargin": info.get("grossMargins"),
        "OperatingMargin": info.get("operatingMargins"),
        "ROE": info.get("returnOnEquity"),
        "FreeCashFlowMargin": divide_or_blank(free_cashflow, total_revenue),
        "DebtToEquity": debt_to_equity_ratio(info.get("debtToEquity")),
        "PE": info.get("trailingPE"),
        "PS": info.get("priceToSalesTrailing12Months"),
    }


def blank_fundamental_row(ticker):
    return {
        column: ticker if column == "Ticker" else None
        for column in OUTPUT_COLUMNS
    }


def load_tickers():
    return get_primary_tickers()


def main():
    tickers = load_tickers()
    rows = []
    failed_tickers = []

    for ticker in tickers:
        print(f"Fetching fundamentals for {ticker} ...")

        try:
            row = build_fundamental_row(ticker)
        except Exception as error:
            failed_tickers.append(ticker)
            row = blank_fundamental_row(ticker)
            print(f"Failed {ticker}: {type(error).__name__}: {error}")

        rows.append(row)

    output_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(OUTPUT_PATH, index=False)

    print("")
    print(f"Tickers processed: {len(tickers)}")
    if failed_tickers:
        print(f"Failed tickers: {', '.join(failed_tickers)}")
    else:
        print("Failed tickers: None")
    print(f"Output path: {display_path(OUTPUT_PATH)}")


if __name__ == "__main__":
    main()
