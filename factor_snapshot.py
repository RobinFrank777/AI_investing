"""Build a deterministic, research-only factor snapshot.

The module deliberately consumes existing production outputs instead of
reimplementing ranking or backtest formulas.  Market-data indicators are
calculated through ``calculate_indicators`` on a defensive copy.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from config import (
    BACKTEST_SUMMARY_20D_OUTPUT_PATH,
    COMBINED_SCORE_OUTPUT_PATH,
    RESULTS_DIR_PATH,
    STOCK_RANK_OUTPUT_PATH,
    display_path,
)
from indicators import calculate_indicators
from price_factors import calculate_price_factors
from stock_loader import load_stock
from universe_source import load_active_universe


FACTOR_SNAPSHOT_OUTPUT_PATH = RESULTS_DIR_PATH / "factor_snapshot.csv"
MIN_FACTOR_ROWS = 60

REQUIRED_COLUMNS = [
    "Ticker", "AsOfDate", "DataRows", "Close", "FactorStatus",
    "MissingFactors", "FactorMessage",
]
OPTIONAL_COLUMNS = [
    "Return20D", "TrendValue", "MomentumValue", "Volatility20D",
    "MA20", "MA60", "ATR14", "RSI14", "MACD",
    "MACDSignal", "MACDHistogram", "TechnicalScore", "BacktestScore",
    "CombinedScore", "MaxDrawdown", "SharpeRatio",
]
SNAPSHOT_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

SOURCE_SPECS = (
    ("technical", STOCK_RANK_OUTPUT_PATH, {
        "20Day_Return": "Return20D", "FinalScore": "TechnicalScore",
    }),
    ("backtest", BACKTEST_SUMMARY_20D_OUTPUT_PATH, {
        "BacktestScore": "BacktestScore", "MaxDrawdown": "MaxDrawdown",
        "SharpeRatio": "SharpeRatio",
    }),
    ("combined", COMBINED_SCORE_OUTPUT_PATH, {
        "CombinedScore": "CombinedScore",
    }),
)


def _symbol(value):
    return str(value).strip().upper()


def _empty_row(symbol):
    row = {column: None for column in SNAPSHOT_COLUMNS}
    row.update({
        "Ticker": _symbol(symbol), "DataRows": 0, "FactorStatus": "FAILED",
        "MissingFactors": ";".join(OPTIONAL_COLUMNS), "FactorMessage": "",
    })
    return row


def _load_optional_sources():
    sources = {}
    for name, path, mapping in SOURCE_SPECS:
        if not Path(path).is_file():
            sources[name] = {"rows": {}, "duplicates": set()}
            continue
        frame = pd.read_csv(path)
        if "Ticker" not in frame.columns:
            sources[name] = {"rows": {}, "duplicates": set()}
            continue
        normalized = frame["Ticker"].map(_symbol)
        duplicates = set(normalized[normalized.duplicated(keep=False)])
        rows = {}
        for index, ticker in normalized.items():
            if ticker and ticker not in duplicates:
                rows[ticker] = {
                    target: frame.at[index, source]
                    for source, target in mapping.items()
                    if source in frame.columns
                }
        sources[name] = {"rows": rows, "duplicates": duplicates}
    return sources


def _valid_number(value):
    return value is not None and not pd.isna(value)


def _build_factor_snapshot(symbol, data, sources):
    """Return one factor row without mutating caller-supplied market data."""
    ticker = _symbol(symbol)
    row = _empty_row(ticker)
    if not ticker:
        row["FactorMessage"] = "Ticker is empty"
        return row

    try:
        market = load_stock(ticker) if data is None else data.copy(deep=True)
    except (FileNotFoundError, OSError):
        row["FactorMessage"] = "Missing market data file"
        return row
    except Exception as error:
        row["FactorMessage"] = f"Market data error: {error}"
        return row

    if not isinstance(market, pd.DataFrame) or market.empty:
        row["FactorMessage"] = "No valid Date/Close rows"
        return row
    missing_required = [name for name in ("Date", "Close") if name not in market]
    if missing_required:
        row["FactorMessage"] = "Missing required column: " + ", ".join(missing_required)
        return row

    working = market.copy(deep=True)
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    working["Close"] = pd.to_numeric(working["Close"], errors="coerce")
    valid = working.dropna(subset=["Date", "Close"])
    if valid.empty:
        row["FactorMessage"] = "No valid Date/Close rows"
        return row
    latest_index = valid["Date"].idxmax()
    row.update({
        "AsOfDate": valid.at[latest_index, "Date"].strftime("%Y-%m-%d"),
        "DataRows": len(valid), "Close": valid.at[latest_index, "Close"],
    })

    messages = []
    try:
        native_factors = calculate_price_factors(working)
        for factor, value in native_factors.items():
            if _valid_number(value):
                row[factor] = value
    except Exception as error:
        messages.append(f"Native price factors unavailable: {error}")

    indicator_inputs = {"High", "Low", "Volume"}
    if indicator_inputs.issubset(working.columns):
        try:
            calculated = calculate_indicators(working.copy(deep=True))
            latest = calculated.loc[latest_index]
            for source, target in (
                ("MA20", "MA20"), ("MA60", "MA60"), ("ATR14", "ATR14"),
                ("RSI14", "RSI14"), ("MACD", "MACD"),
                ("MACD_Signal", "MACDSignal"), ("Histogram", "MACDHistogram"),
            ):
                if _valid_number(latest[source]):
                    row[target] = latest[source]
        except Exception as error:
            messages.append(f"Indicator calculation unavailable: {error}")
    else:
        messages.append("Indicator inputs missing")

    for name, _, _ in SOURCE_SPECS:
        source = sources[name]
        if ticker in source["duplicates"]:
            messages.append(f"Duplicate ticker in {name} source")
            continue
        for target, value in source["rows"].get(ticker, {}).items():
            if _valid_number(value):
                row[target] = value

    missing = [column for column in OPTIONAL_COLUMNS if not _valid_number(row[column])]
    row["MissingFactors"] = ";".join(missing)
    if len(valid) < MIN_FACTOR_ROWS:
        messages.append(f"Insufficient history: {len(valid)} rows; {MIN_FACTOR_ROWS} required for MA60")
    row["FactorStatus"] = "PASS" if not missing else "PARTIAL"
    row["FactorMessage"] = "; ".join(messages)
    return row


def build_factor_snapshot(symbol, data=None, *, include_runtime_sources=True):
    """Return one factor row with optional current production-result fields."""
    sources = _load_optional_sources() if include_runtime_sources else {
        name: {"rows": {}, "duplicates": set()} for name, _, _ in SOURCE_SPECS
    }
    return _build_factor_snapshot(symbol, data, sources)


def build_factor_snapshot_table(symbols=None, *, include_runtime_sources=True):
    """Build one row per requested symbol, preserving source order."""
    requested = load_active_universe() if symbols is None else symbols
    sources = _load_optional_sources() if include_runtime_sources else {
        name: {"rows": {}, "duplicates": set()} for name, _, _ in SOURCE_SPECS
    }
    rows = []
    for symbol in requested:
        try:
            rows.append(_build_factor_snapshot(symbol, None, sources))
        except Exception as error:
            row = _empty_row(symbol)
            row["FactorMessage"] = f"Unexpected symbol error: {error}"
            rows.append(row)
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def save_factor_snapshot(
    symbols=None, output_path=None, *, include_runtime_sources=True
):
    """Write the snapshot as UTF-8 CSV and return its Path."""
    path = FACTOR_SNAPSHOT_OUTPUT_PATH if output_path is None else Path(output_path)
    table = build_factor_snapshot_table(
        symbols, include_runtime_sources=include_runtime_sources
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, encoding="utf-8")
    return path


def _parser():
    parser = argparse.ArgumentParser(description="Build the Factor Snapshot")
    parser.add_argument("--symbol", action="append", help="Limit output to a symbol")
    parser.add_argument("--output", type=Path, help="Output CSV path")
    return parser


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
        path = save_factor_snapshot(args.symbol, args.output)
        table = pd.read_csv(path)
        counts = table["FactorStatus"].value_counts()
        print("Factor Snapshot")
        print(f"Symbols: {len(table)}")
        for status in ("PASS", "PARTIAL", "FAILED"):
            print(f"{status}: {int(counts.get(status, 0))}")
        print(f"Output: {display_path(path)}")
        return 0
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Factor Snapshot error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
