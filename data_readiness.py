"""Canonical market-data readiness audit for the Primary Universe."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from config import PRIMARY_UNIVERSE_PATH, PRIMARY_UNIVERSE_VERSION
from stock_loader import (
    NUMERIC_COLUMNS,
    PRICE_COLUMNS,
    REQUIRED_COLUMNS,
    load_stock_file,
)
from universe_loader import get_primary_tickers, load_universe


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_data_quality.csv"
MINIMUM_HISTORY_ROWS = 252
READINESS_COLUMNS = (
    "Ticker",
    "UniverseVersion",
    "FilePath",
    "FileExists",
    "Rows",
    "FirstDate",
    "LastDate",
    "MissingValues",
    "DuplicateDates",
    "InvalidNumeric",
    "InvalidOHLC",
    "ParseError",
    "MinimumHistoryPass",
    "Ready",
    "Reason",
    "Status",
    "LatestAcceptedDate",
    "RequiredAsOfDate",
    "ProviderRejectedDate",
)


def _base_record(ticker, path):
    return {
        "Ticker": str(ticker).strip().upper(),
        "UniverseVersion": PRIMARY_UNIVERSE_VERSION,
        "FilePath": str(path),
        "FileExists": path.is_file(),
        "Rows": 0,
        "FirstDate": "",
        "LastDate": "",
        "MissingValues": 0,
        "DuplicateDates": 0,
        "InvalidNumeric": 0,
        "InvalidOHLC": 0,
        "ParseError": "",
        "MinimumHistoryPass": False,
        "Ready": False,
        "Reason": "",
        "Status": "NOT_READY",
        "LatestAcceptedDate": "",
        "RequiredAsOfDate": "",
        "ProviderRejectedDate": "",
    }


def _invalid_ohlc_count(frame):
    numeric = frame.loc[:, NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    finite = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
    valid = numeric.loc[finite]
    if valid.empty:
        return 0
    invalid = (
        (valid[PRICE_COLUMNS] <= 0).any(axis=1)
        | (valid["Volume"] < 0)
        | (valid["High"] < valid[["Open", "Close", "Low"]].max(axis=1))
        | (valid["Low"] > valid[["Open", "Close", "High"]].min(axis=1))
    )
    return int(invalid.sum())


def inspect_price_file(ticker, data_dir=None):
    """Return one stable readiness record without changing market data."""
    root = DEFAULT_DATA_DIR if data_dir is None else Path(data_dir)
    path = root / f"{str(ticker).strip().upper()}.csv"
    record = _base_record(ticker, path)
    if not record["FileExists"]:
        record["Reason"] = "MISSING_FILE"
        return record

    try:
        raw = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        record["ParseError"] = "Price file is empty"
        record["Reason"] = "PARSE_ERROR"
        return record
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        record["ParseError"] = f"{type(error).__name__}: {error}"
        record["Reason"] = "PARSE_ERROR"
        return record
    except Exception as error:
        record["ParseError"] = f"{type(error).__name__}: {error}"
        record["Reason"] = "PARSE_ERROR"
        return record

    record["Rows"] = int(len(raw))
    record["MinimumHistoryPass"] = len(raw) >= MINIMUM_HISTORY_ROWS
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in raw]
    if missing_columns:
        record["Reason"] = "OTHER_VALIDATION_ERROR:MISSING_COLUMNS:" + ",".join(
            missing_columns
        )
        return record

    selected = raw.loc[:, REQUIRED_COLUMNS]
    record["MissingValues"] = int(selected.isna().sum().sum())
    dates = pd.to_datetime(selected["Date"], errors="coerce")
    valid_dates = dates.dropna()
    if not valid_dates.empty:
        record["FirstDate"] = valid_dates.iloc[0].strftime("%Y-%m-%d")
        record["LastDate"] = valid_dates.iloc[-1].strftime("%Y-%m-%d")
    record["DuplicateDates"] = int(valid_dates.duplicated().sum())

    numeric = selected.loc[:, NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    record["InvalidNumeric"] = int(
        (~np.isfinite(numeric.to_numpy(dtype=float))).sum()
    )
    record["InvalidOHLC"] = _invalid_ohlc_count(selected)

    reasons = []
    if not record["MinimumHistoryPass"]:
        reasons.append("INSUFFICIENT_HISTORY")
    if record["DuplicateDates"]:
        reasons.append("DUPLICATE_DATES")
    if record["InvalidNumeric"]:
        reasons.append("INVALID_NUMERIC")
    if record["InvalidOHLC"]:
        reasons.append("INVALID_OHLC")
    if dates.isna().any():
        reasons.append("OTHER_VALIDATION_ERROR:INVALID_DATE")
    elif not dates.is_monotonic_increasing:
        reasons.append("OTHER_VALIDATION_ERROR:DATE_ORDER")

    try:
        load_stock_file(path, ticker=record["Ticker"])
    except (ValueError, TypeError, OSError, UnicodeError, pd.errors.ParserError) as error:
        if not reasons:
            reasons.append(f"OTHER_VALIDATION_ERROR:{type(error).__name__}")

    record["Ready"] = not reasons
    record["Reason"] = "|".join(reasons) if reasons else "READY"
    return record


def build_data_readiness(universe_path=None, data_dir=None, *, required_as_of=None,
                         refresh_results=None):
    """Audit every configured Primary Universe member in file order."""
    universe = load_universe(
        PRIMARY_UNIVERSE_PATH if universe_path is None else universe_path
    )
    records = [
        inspect_price_file(ticker, data_dir=data_dir)
        for ticker in get_primary_tickers(universe)
    ]
    readiness = pd.DataFrame(records, columns=READINESS_COLUMNS)
    valid_dates = pd.to_datetime(readiness["LastDate"], errors="coerce")
    required = (
        valid_dates.max() if required_as_of is None
        else pd.Timestamp(required_as_of).normalize()
    )
    readiness["LatestAcceptedDate"] = readiness["LastDate"]
    readiness["RequiredAsOfDate"] = "" if pd.isna(required) else required.strftime("%Y-%m-%d")
    stale = readiness["Ready"] & valid_dates.notna() & (valid_dates < required)
    readiness.loc[stale, "Ready"] = False
    readiness.loc[stale, "Reason"] = "STALE_MARKET_DATA"
    readiness["Status"] = "READY"
    readiness.loc[readiness["Reason"].str.contains("INSUFFICIENT_HISTORY", regex=False), "Status"] = "INSUFFICIENT_HISTORY"
    readiness.loc[readiness["Reason"].eq("STALE_MARKET_DATA"), "Status"] = "STALE_MARKET_DATA"
    readiness.loc[~readiness["Ready"] & ~readiness["Status"].isin(
        {"INSUFFICIENT_HISTORY", "STALE_MARKET_DATA"}
    ), "Status"] = "INVALID_CANONICAL_DATA"
    for ticker, result in (refresh_results or {}).items():
        if result.get("status") != "provider_rejected":
            continue
        mask = readiness["Ticker"].eq(str(ticker).strip().upper())
        quarantinable = mask & ~readiness["Status"].eq("INVALID_CANONICAL_DATA")
        readiness.loc[quarantinable, "Ready"] = False
        readiness.loc[quarantinable, "Reason"] = "PROVIDER_REJECTED_CURRENT_SESSION"
        readiness.loc[quarantinable, "Status"] = "PROVIDER_REJECTED"
        rejected = result.get("rejected_dates") or []
        readiness.loc[mask, "ProviderRejectedDate"] = ",".join(rejected)
    return readiness


def readiness_summary(readiness):
    """Return stable mutually useful counts for a readiness artifact."""
    reasons = readiness["Reason"].fillna("").astype(str)
    ready = int(readiness["Ready"].sum()) if not readiness.empty else 0
    contains = lambda value: int(reasons.str.contains(value, regex=False).sum())
    known = (
        reasons.str.contains("MISSING_FILE|PARSE_ERROR|INSUFFICIENT_HISTORY|"
                             "DUPLICATE_DATES|INVALID_OHLC|INVALID_NUMERIC|"
                             "STALE_MARKET_DATA", regex=True)
    )
    return {
        "configured": int(len(readiness)),
        "ready": ready,
        "not_ready": int(len(readiness) - ready),
        "missing_file": contains("MISSING_FILE"),
        "parse_error": contains("PARSE_ERROR"),
        "insufficient_history": contains("INSUFFICIENT_HISTORY"),
        "duplicate_date_failure": contains("DUPLICATE_DATES"),
        "invalid_ohlc": contains("INVALID_OHLC"),
        "invalid_numeric": contains("INVALID_NUMERIC"),
        "stale_market_data": contains("STALE_MARKET_DATA"),
        "provider_rejected": int(readiness["Status"].eq("PROVIDER_REJECTED").sum()),
        "other_failure": int(((~readiness["Ready"]) & ~known).sum()),
    }


def save_data_readiness(readiness, output_path=None):
    """Save an already-built readiness table without changing source data."""
    if not isinstance(readiness, pd.DataFrame):
        raise TypeError("readiness must be a pandas DataFrame")
    missing = [column for column in READINESS_COLUMNS if column not in readiness]
    if missing:
        raise ValueError("readiness is missing columns: " + ", ".join(missing))
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    readiness.loc[:, READINESS_COLUMNS].to_csv(path, index=False)
    return path


def load_readiness_context(path=None):
    """Return compact disclosure context from the canonical readiness artifact."""
    source = DEFAULT_OUTPUT_PATH if path is None else Path(path)
    if not source.is_file():
        return None
    try:
        frame = pd.read_csv(source)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeError):
        return None
    required = {"Ticker", "Ready", "Status", "Reason", "RequiredAsOfDate"}
    if frame.empty or not required.issubset(frame.columns):
        return None
    ready = frame["Ready"]
    if ready.dtype != bool:
        ready = ready.astype(str).str.upper().map({"TRUE": True, "FALSE": False}).fillna(False)
    excluded = frame.loc[~ready]
    return {
        "ConfiguredUniverseCount": int(len(frame)),
        "ResearchReadyCount": int(ready.sum()),
        "ExcludedUniverseCount": int((~ready).sum()),
        "ProviderRejectedCount": int(frame["Status"].eq("PROVIDER_REJECTED").sum()),
        "StaleMarketDataCount": int(frame["Status"].eq("STALE_MARKET_DATA").sum()),
        "InsufficientHistoryCount": int(frame["Status"].eq("INSUFFICIENT_HISTORY").sum()),
        "RequiredAsOfDate": str(frame["RequiredAsOfDate"].dropna().iloc[0]) if frame["RequiredAsOfDate"].notna().any() else "MISSING",
        "ExcludedSymbols": ", ".join(
            f"{row.Ticker} ({row.Status})" for row in excluded.itertuples(index=False)
        ) or "None",
    }


def run_data_readiness(universe_path=None, data_dir=None, output_path=None):
    readiness = build_data_readiness(universe_path=universe_path, data_dir=data_dir)
    path = save_data_readiness(readiness, output_path=output_path)
    return {
        "readiness": readiness,
        "summary": readiness_summary(readiness),
        "output_path": str(path),
    }


def main():
    try:
        result = run_data_readiness()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 data readiness error: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print("AI_investing Universe150 Data Readiness")
    for label, key in (("Configured", "configured"), ("Ready", "ready"), ("Not ready", "not_ready")):
        print(f"{label}: {summary[key]}")
    print(f"Output: {result['output_path']}")
    print("Readiness does not change Primary Universe membership.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
