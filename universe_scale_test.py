"""Offline-first validation for a small, explicit expansion universe."""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

import update_data
from config import DATA_DIR_PATH, display_path
from universe_manager import load_universe


DEFAULT_UNIVERSE_PATH = DATA_DIR_PATH / "universes" / "scale50.example.csv"


def load_scale_test_universe(file_path):
    """Load an explicit test universe through the canonical manager."""
    return load_universe(file_path)


def _invalid_entry(symbol, file_path, reasons):
    return {"symbol": symbol, "file_path": file_path, "reasons": reasons}


def inspect_local_data(symbols, data_dir=None):
    """Inspect target CSV files without modifying them or accessing the network."""
    symbol_list = list(symbols)
    target_dir = Path(data_dir) if data_dir is not None else DATA_DIR_PATH
    existing_files = 0
    valid_files = 0
    total_bytes = 0
    latest_dates = {}
    symbols_with_data = []
    symbols_missing_data = []
    invalid_entries = []
    warnings = []

    for symbol in symbol_list:
        file_path = target_dir / f"{symbol}.csv"
        if not file_path.is_file():
            symbols_missing_data.append(symbol)
            continue

        existing_files += 1
        try:
            total_bytes += file_path.stat().st_size
        except OSError as error:
            invalid_entries.append(
                _invalid_entry(symbol, file_path, [f"Unable to stat file: {error}"])
            )
            continue

        try:
            frame = pd.read_csv(file_path)
        except Exception as error:
            invalid_entries.append(
                _invalid_entry(symbol, file_path, [f"Unable to read CSV: {error}"])
            )
            continue

        reasons = []
        if frame.empty:
            reasons.append("CSV file contains no data.")
        if "Date" not in frame.columns:
            reasons.append("Missing required column: Date")
        if "Close" not in frame.columns:
            reasons.append("Missing required column: Close")

        if reasons:
            invalid_entries.append(_invalid_entry(symbol, file_path, reasons))
            continue

        parsed_dates = pd.to_datetime(frame["Date"], errors="coerce")
        parsed_close = pd.to_numeric(frame["Close"], errors="coerce")
        usable_rows = parsed_dates.notna() & parsed_close.notna()
        invalid_date_count = int(parsed_dates.isna().sum())
        if invalid_date_count:
            warnings.append(
                f"{symbol}: ignored {invalid_date_count} invalid Date value(s)."
            )
        if not usable_rows.any():
            invalid_entries.append(
                _invalid_entry(
                    symbol,
                    file_path,
                    ["CSV contains no row with a valid Date and Close value."],
                )
            )
            continue

        latest_date = parsed_dates[usable_rows].max().strftime("%Y-%m-%d")
        latest_dates[symbol] = latest_date
        symbols_with_data.append(symbol)
        valid_files += 1

    if not symbol_list:
        warnings.append("Scale test universe contains no enabled symbols.")

    return {
        "symbol_count": len(symbol_list),
        "existing_files": existing_files,
        "missing_files": len(symbols_missing_data),
        "valid_files": valid_files,
        "invalid_files": len(invalid_entries),
        "total_bytes": total_bytes,
        "latest_dates": latest_dates,
        "symbols_with_data": symbols_with_data,
        "symbols_missing_data": symbols_missing_data,
        "invalid_entries": invalid_entries,
        "warnings": warnings,
    }


def _validate_limit(limit):
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer.")
    return limit


def run_scale_validation(universe_path, data_dir=None, download=False, limit=None):
    """Run an offline inspection, optionally preceded by explicit serial downloads."""
    started = time.monotonic()
    selected_limit = _validate_limit(limit)
    source_path = Path(universe_path)
    symbols = load_scale_test_universe(source_path)
    if selected_limit is not None:
        symbols = symbols[:selected_limit]

    target_dir = Path(data_dir) if data_dir is not None else DATA_DIR_PATH
    download_summary = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "failed_symbols": [],
        "elapsed_seconds": 0.0,
        "average_seconds_per_symbol": 0.0,
    }

    if download:
        target_dir.mkdir(parents=True, exist_ok=True)
        download_started = time.monotonic()
        original_data_dir = update_data.DATA_DIR
        update_data.DATA_DIR = target_dir
        try:
            for symbol in symbols:
                download_summary["attempted"] += 1
                try:
                    update_data.update_one_stock(symbol)
                    download_summary["succeeded"] += 1
                except Exception:
                    download_summary["failed"] += 1
                    download_summary["failed_symbols"].append(symbol)
        finally:
            update_data.DATA_DIR = original_data_dir

        download_elapsed = time.monotonic() - download_started
        download_summary["elapsed_seconds"] = download_elapsed
        if download_summary["attempted"]:
            download_summary["average_seconds_per_symbol"] = (
                download_elapsed / download_summary["attempted"]
            )

    local_summary = inspect_local_data(symbols, target_dir)
    elapsed_seconds = time.monotonic() - started
    return {
        "universe_path": source_path,
        "download_enabled": bool(download),
        "symbol_count": len(symbols),
        "symbols": symbols,
        "existing_files": local_summary["existing_files"],
        "missing_files": local_summary["missing_files"],
        "valid_files": local_summary["valid_files"],
        "invalid_files": local_summary["invalid_files"],
        "total_bytes": local_summary["total_bytes"],
        "latest_dates": local_summary["latest_dates"],
        "symbols_with_data": local_summary["symbols_with_data"],
        "symbols_missing_data": local_summary["symbols_missing_data"],
        "invalid_entries": local_summary["invalid_entries"],
        "elapsed_seconds": elapsed_seconds,
        "download_summary": download_summary,
        "warnings": local_summary["warnings"],
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
    parser = argparse.ArgumentParser(description="Validate a small test universe.")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE_PATH)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--limit", type=_positive_int)
    return parser


def _print_summary(report):
    print("Universe Scale Validation")
    print(f"Universe: {display_path(report['universe_path'])}")
    print(f"Symbols: {report['symbol_count']}")
    print(f"Existing Files: {report['existing_files']}")
    print(f"Missing Files: {report['missing_files']}")
    print(f"Valid Files: {report['valid_files']}")
    print(f"Invalid Files: {report['invalid_files']}")
    print(f"Disk Usage: {report['total_bytes'] / (1024 * 1024):.2f} MB")
    print(f"Elapsed: {report['elapsed_seconds']:.2f} seconds")
    print(f"Download: {'enabled' if report['download_enabled'] else 'disabled'}")
    if report["download_enabled"]:
        download = report["download_summary"]
        print(f"Attempted: {download['attempted']}")
        print(f"Succeeded: {download['succeeded']}")
        print(f"Failed: {download['failed']}")
        print(
            "Average Time: "
            f"{download['average_seconds_per_symbol']:.2f} seconds/symbol"
        )
        print(
            "Failed Symbols: "
            + (", ".join(download["failed_symbols"]) or "None")
        )
    if report["warnings"]:
        print("Warnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")


def main(argv=None):
    arguments = _build_parser().parse_args(argv)
    try:
        report = run_scale_validation(
            arguments.universe,
            download=arguments.download,
            limit=arguments.limit,
        )
        _print_summary(report)
    except (FileNotFoundError, ValueError) as error:
        print(f"Universe scale validation error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
