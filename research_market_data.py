"""Research-only market-data preparation for the Universe150 universe."""

import argparse
import sys

import pandas as pd

import data_readiness
import universe_loader
import update_data


ALLOWED_DOWNLOAD_STATUSES = frozenset({"success", "empty", "failed"})


def _validate_limit(limit):
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    return limit


def select_download_candidates(readiness, active_symbols, *, limit=None):
    """Select missing ACTIVE symbols in universe order without overwriting files."""
    selected_limit = _validate_limit(limit)
    if not isinstance(readiness, pd.DataFrame):
        raise TypeError("readiness must be a pandas DataFrame")
    required = {"Ticker", "FileExists"}
    missing_columns = sorted(required - set(readiness.columns))
    if missing_columns:
        raise ValueError(
            "readiness is missing required columns: " + ", ".join(missing_columns)
        )

    file_exists = {
        str(row.Ticker): bool(row.FileExists)
        for row in readiness[["Ticker", "FileExists"]].itertuples(index=False)
    }
    candidates = [
        symbol
        for symbol in active_symbols
        if symbol in file_exists and not file_exists[symbol]
    ]
    return candidates if selected_limit is None else candidates[:selected_limit]


def _failed_result(symbol, message):
    return {
        "symbol": symbol,
        "status": "failed",
        "rows": 0,
        "latest_date": None,
        "output_path": None,
        "message": message,
    }


def _normalize_download_result(symbol, result):
    if not isinstance(result, dict):
        return _failed_result(
            symbol,
            f"Malformed downloader result: expected dict, got {type(result).__name__}",
        )
    status = result.get("status")
    if status not in ALLOWED_DOWNLOAD_STATUSES:
        return _failed_result(symbol, f"Malformed downloader status: {status!r}")
    normalized = {
        "symbol": symbol,
        "status": status,
        "rows": result.get("rows", 0),
        "latest_date": result.get("latest_date"),
        "output_path": result.get("output_path"),
        "message": str(result.get("message") or ""),
    }
    returned_symbol = result.get("symbol")
    if returned_symbol not in (None, symbol):
        return _failed_result(
            symbol,
            f"Downloader returned symbol {returned_symbol!r} for {symbol!r}",
        )
    return normalized


def _readiness_counts(readiness):
    if readiness.empty:
        return {"total": 0, "ready": 0, "missing": 0, "invalid": 0, "insufficient": 0}
    exists = readiness["FileExists"].astype(bool)
    columns_present = readiness["RequiredColumnsPresent"].astype(bool)
    history_sufficient = readiness["HistorySufficient"].astype(bool)
    ready = readiness["Ready"].astype(bool)
    return {
        "total": int(len(readiness)),
        "ready": int(ready.sum()),
        "missing": int((~exists).sum()),
        "invalid": int((exists & ~columns_present).sum()),
        "insufficient": int((exists & columns_present & ~history_sufficient).sum()),
    }


def run_research_market_data(
    universe_path=None, *, download=False, limit=None, output_path=None
):
    """Inspect Universe150 and optionally download missing files serially."""
    selected_limit = _validate_limit(limit)
    universe = universe_loader.load_universe(universe_path)
    active_symbols = universe_loader.get_active_symbols(universe)
    initial_readiness = data_readiness.build_data_readiness(
        universe_path=universe_path
    )
    candidates = select_download_candidates(
        initial_readiness, active_symbols, limit=selected_limit
    )

    download_results = []
    if download:
        for symbol in candidates:
            try:
                raw_result = update_data.update_one_stock(symbol)
                result = _normalize_download_result(symbol, raw_result)
            except Exception as error:
                result = _failed_result(
                    symbol, f"Downloader raised {type(error).__name__}: {error}"
                )
            download_results.append(result)

    final_readiness = data_readiness.build_data_readiness(
        universe_path=universe_path
    )
    saved_path = data_readiness.save_data_readiness(
        final_readiness, output_path=output_path
    )
    status_counts = {
        status: sum(result["status"] == status for result in download_results)
        for status in ("success", "empty", "failed")
    }
    return {
        "download_enabled": bool(download),
        "active_symbols": active_symbols,
        "initial_readiness": initial_readiness,
        "candidates": candidates,
        "download_results": download_results,
        "final_readiness": final_readiness,
        "output_path": str(saved_path),
        "summary": {
            "initial": _readiness_counts(initial_readiness),
            "final": _readiness_counts(final_readiness),
            "attempted": len(download_results),
            **status_counts,
        },
    }


def _positive_int(value):
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    return number


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Prepare Universe150 research market data."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect-only", action="store_true")
    mode.add_argument("--download", action="store_true")
    parser.add_argument("--limit", type=_positive_int)
    return parser


def main(argv=None):
    arguments = _build_parser().parse_args(argv)
    try:
        result = run_research_market_data(
            download=arguments.download, limit=arguments.limit
        )
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 market-data preparation error: {error}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("AI_investing Universe150 Market Data Preparation")
    print(f"Mode: {'download' if result['download_enabled'] else 'inspect only'}")
    print(f"Active symbols: {len(result['active_symbols'])}")
    print(f"Ready: {summary['final']['ready']}")
    print(f"Missing: {summary['final']['missing']}")
    print(f"Invalid: {summary['final']['invalid']}")
    print(f"Insufficient history: {summary['final']['insufficient']}")
    print(f"Attempted: {summary['attempted']}")
    print(f"Failed: {summary['failed']}")
    print(f"Output: {result['output_path']}")
    print("Research preparation only; no production or trading workflow was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
