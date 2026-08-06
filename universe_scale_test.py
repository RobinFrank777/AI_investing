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


def _file_state(file_path):
    exists = file_path.is_file()
    if not exists:
        return {"exists": False, "bytes": None}
    try:
        return {"exists": True, "bytes": file_path.stat().st_size}
    except OSError:
        return {"exists": True, "bytes": None}


def _failed_download_result(symbol, message, output_path):
    return {
        "symbol": symbol,
        "status": "failed",
        "rows": 0,
        "latest_date": None,
        "output_path": output_path,
        "message": message,
    }


def _normalize_download_result(symbol, raw_result, output_path):
    """Normalize one downloader response without mutating the original value."""
    problems = []
    if not isinstance(raw_result, dict):
        kind = "None" if raw_result is None else type(raw_result).__name__
        message = f"Malformed download result for {symbol}: expected dict, got {kind}."
        return _failed_download_result(symbol, message, output_path), message

    returned_symbol = raw_result.get("symbol")
    if not returned_symbol:
        problems.append("missing symbol")
    elif returned_symbol != symbol:
        problems.append(
            f"returned symbol {returned_symbol!r} does not match requested symbol"
        )

    status = raw_result.get("status")
    if status not in {"success", "empty", "failed"}:
        problems.append(f"unsupported or missing status {status!r}")

    rows = raw_result.get("rows", 0)
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
        problems.append(f"invalid rows value {rows!r}")
        rows = 0

    latest_date = raw_result.get("latest_date")
    if latest_date is not None:
        latest_date = str(latest_date)
    returned_path = raw_result.get("output_path")
    normalized_path = str(returned_path) if returned_path is not None else None
    message = str(raw_result.get("message") or "")

    if status == "success":
        if rows <= 0:
            problems.append("success result must contain rows > 0")
        if not returned_path:
            problems.append("success result must contain output_path")
    elif status == "empty" and rows != 0:
        problems.append("empty result must contain rows = 0")
    elif status == "failed" and not message:
        problems.append("failed result must contain an error message")

    if problems:
        warning = f"Malformed download result for {symbol}: " + "; ".join(problems) + "."
        return _failed_download_result(
            symbol, warning, normalized_path or output_path
        ), warning

    return {
        "symbol": symbol,
        "status": status,
        "rows": rows,
        "latest_date": latest_date,
        "output_path": normalized_path,
        "message": message,
    }, None


def _empty_download_summary():
    return {
        "attempted": 0,
        "succeeded": 0,
        "empty": 0,
        "failed": 0,
        "successful_symbols": [],
        "empty_symbols": [],
        "failed_symbols": [],
        "results": [],
        "elapsed_seconds": 0.0,
        "average_seconds_per_symbol": 0.0,
    }


def run_scale_validation(universe_path, data_dir=None, download=False, limit=None):
    """Run an offline inspection, optionally preceded by explicit serial downloads."""
    started = time.monotonic()
    selected_limit = _validate_limit(limit)
    source_path = Path(universe_path)
    symbols = load_scale_test_universe(source_path)
    if selected_limit is not None:
        symbols = symbols[:selected_limit]

    target_dir = Path(data_dir) if data_dir is not None else DATA_DIR_PATH
    download_summary = _empty_download_summary()
    download_warnings = []

    if download:
        target_dir.mkdir(parents=True, exist_ok=True)
        download_started = time.monotonic()
        original_data_dir = update_data.DATA_DIR
        update_data.DATA_DIR = target_dir
        try:
            for symbol in symbols:
                download_summary["attempted"] += 1
                output_file = target_dir / f"{symbol}.csv"
                before = _file_state(output_file)
                symbol_started = time.monotonic()
                try:
                    raw_result = update_data.update_one_stock(symbol)
                    normalized, warning = _normalize_download_result(
                        symbol, raw_result, str(output_file)
                    )
                except Exception as error:
                    message = f"Download raised {type(error).__name__}: {error}"
                    normalized = _failed_download_result(
                        symbol, message, str(output_file)
                    )
                    warning = None

                after = _file_state(output_file)
                normalized.update(
                    {
                        "elapsed_seconds": time.monotonic() - symbol_started,
                        "file_existed_before": before["exists"],
                        "file_exists_after": after["exists"],
                        "bytes_before": before["bytes"],
                        "bytes_after": after["bytes"],
                    }
                )
                download_summary["results"].append(normalized)
                if warning:
                    download_warnings.append(warning)

                status = normalized["status"]
                if status == "success":
                    download_summary["succeeded"] += 1
                    download_summary["successful_symbols"].append(symbol)
                elif status == "empty":
                    download_summary["empty"] += 1
                    download_summary["empty_symbols"].append(symbol)
                else:
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
    locally_valid = set(local_summary["symbols_with_data"])
    for symbol in download_summary["successful_symbols"]:
        if symbol not in locally_valid:
            download_warnings.append(
                f"{symbol}: download reported success but local data validation failed."
            )
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
        "warnings": local_summary["warnings"] + download_warnings,
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
        print("Download Results")
        print(f"Attempted: {download['attempted']}")
        print(f"Succeeded: {download['succeeded']}")
        print(f"Empty: {download['empty']}")
        print(f"Failed: {download['failed']}")
        print(f"Elapsed: {download['elapsed_seconds']:.2f} seconds")
        print(
            "Average Per Symbol: "
            f"{download['average_seconds_per_symbol']:.2f} seconds"
        )
        print("Per-Symbol Results:")
        for result in download["results"]:
            print(
                f"{result['symbol']}  {result['status']}  "
                f"rows={result['rows']}  latest={result['latest_date']}"
            )
        if download["empty_symbols"]:
            print("Empty Symbols:")
            for symbol in download["empty_symbols"]:
                print(symbol)
        if download["failed_symbols"]:
            print("Failed Symbols:")
            failed_results = {
                result["symbol"]: result for result in download["results"]
            }
            for symbol in download["failed_symbols"]:
                print(f"{symbol}: {failed_results[symbol]['message']}")
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
