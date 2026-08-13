"""Deterministic loading and validation for the market universe."""

import re
import sys
from pathlib import Path

import pandas as pd

from config import PRIMARY_UNIVERSE_PATH, display_path
import universe_loader


TICKER_COLUMN = "Ticker"
ENABLED_COLUMN = "Enabled"
ENABLED_VALUES = {"true", "1", "yes", "y", "enabled", "active"}
DISABLED_VALUES = {"false", "0", "no", "n", "disabled", "inactive"}
TICKER_PATTERN = re.compile(r"^[A-Z0-9.-]{1,15}$")


def _read_universe(path):
    """Read a universe CSV and translate parser failures into a clear error."""
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        # A physically empty file is still useful to the validation command: it
        # represents an empty universe rather than a corrupt CSV.
        return pd.DataFrame(columns=[TICKER_COLUMN])
    except Exception as error:
        raise ValueError(f"Unable to read market universe CSV: {path}") from error


def _normalized_text(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def _enabled_state(value):
    if value is None or pd.isna(value):
        return False, True

    normalized = str(value).strip().lower()
    if normalized in ENABLED_VALUES:
        return True, True
    if normalized in DISABLED_VALUES or not normalized:
        return False, True
    return False, False


def validate_universe(file_path=None):
    """Return a stable, serializable validation summary for a universe CSV."""
    if file_path is None:
        frame = universe_loader.load_universe()
        symbols = universe_loader.get_primary_tickers(frame)
        return {
            "source_path": PRIMARY_UNIVERSE_PATH,
            "total_rows": len(frame),
            "enabled_rows": len(frame),
            "valid_symbols": len(symbols),
            "duplicate_rows": 0,
            "invalid_rows": 0,
            "disabled_rows": 0,
            "symbols": symbols,
            "duplicates": [],
            "invalid_entries": [],
            "warnings": [],
        }

    source_path = Path(file_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Market universe file not found: {source_path}")

    frame = _read_universe(source_path)
    if TICKER_COLUMN not in frame.columns:
        raise ValueError(
            f"Market universe CSV is missing required column: {TICKER_COLUMN}"
        )

    has_enabled = ENABLED_COLUMN in frame.columns
    symbols = []
    seen = set()
    duplicates = []
    invalid_entries = []
    warnings = []
    enabled_rows = 0
    disabled_rows = 0
    duplicate_rows = 0

    for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
        if has_enabled:
            is_enabled, is_recognized = _enabled_state(row[ENABLED_COLUMN])
            if not is_recognized:
                warnings.append(
                    f"Row {row_number}: unrecognized Enabled value "
                    f"{row[ENABLED_COLUMN]!r}; treated as disabled."
                )
        else:
            is_enabled = True

        if not is_enabled:
            disabled_rows += 1
            continue

        enabled_rows += 1
        symbol = _normalized_text(row[TICKER_COLUMN])
        if not symbol:
            continue
        if not TICKER_PATTERN.fullmatch(symbol):
            invalid_entries.append(
                {
                    "row": row_number,
                    "value": row[TICKER_COLUMN],
                    "normalized": symbol,
                    "reason": "Ticker must use 1-15 letters, digits, dots, or hyphens.",
                }
            )
            continue
        if symbol in seen:
            duplicate_rows += 1
            if symbol not in duplicates:
                duplicates.append(symbol)
            continue

        seen.add(symbol)
        symbols.append(symbol)

    if not symbols:
        warnings.append("No valid enabled ticker symbols were found.")

    return {
        "source_path": source_path,
        "total_rows": len(frame),
        "enabled_rows": enabled_rows,
        "valid_symbols": len(symbols),
        "duplicate_rows": duplicate_rows,
        "invalid_rows": len(invalid_entries),
        "disabled_rows": disabled_rows,
        "symbols": symbols,
        "duplicates": duplicates,
        "invalid_entries": invalid_entries,
        "warnings": warnings,
    }


def load_universe(file_path=None):
    """Load normalized, enabled, valid ticker symbols in first-seen order."""
    return validate_universe(file_path)["symbols"]


def _print_summary(summary):
    print("Market Universe Validation")
    print(f"Source: {display_path(summary['source_path'])}")
    print(f"Rows: {summary['total_rows']}")
    print(f"Enabled: {summary['enabled_rows']}")
    print(f"Valid Symbols: {summary['valid_symbols']}")
    print(f"Duplicates: {summary['duplicate_rows']}")
    print(f"Invalid: {summary['invalid_rows']}")
    print(f"Disabled: {summary['disabled_rows']}")
    print("\nSymbols:")
    for symbol in summary["symbols"]:
        print(symbol)

    if summary["invalid_entries"]:
        print("\nInvalid entries:")
        for entry in summary["invalid_entries"]:
            print(f"- Row {entry['row']}: {entry['value']!r} ({entry['reason']})")
    if summary["warnings"]:
        print("\nWarnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")


def main():
    try:
        _print_summary(validate_universe())
    except (FileNotFoundError, ValueError) as error:
        print(f"Market universe validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
