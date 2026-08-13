"""Load and validate the canonical AI_investing primary universe."""

import sys
from pathlib import Path

import pandas as pd

from config import PRIMARY_UNIVERSE_PATH, PRIMARY_UNIVERSE_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent
# Compatibility alias for existing research callers.  The configured path is
# authoritative; this module does not maintain a second universe setting.
DEFAULT_UNIVERSE_PATH = PRIMARY_UNIVERSE_PATH
REQUIRED_COLUMNS = (
    "order",
    "ticker",
    "company",
    "sector",
    "industry",
    "theme",
    "layer",
    "priority",
    "status",
    "asset_type",
    "notes",
)
ALLOWED_STATUSES = frozenset({"ACTIVE", "WATCH"})
ALLOWED_LAYERS = frozenset({"A", "B", "C"})


def _clean_text(series):
    """Return stripped strings while preserving missing values as empty text."""
    return series.fillna("").astype(str).str.strip()


def load_universe(input_path=None):
    """Load and validate a research-universe CSV as a pandas DataFrame."""
    path = DEFAULT_UNIVERSE_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Research universe file not found: {path}")

    try:
        universe = pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Research universe file is empty: {path}") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"Research universe file is invalid: {path}") from error

    if universe.empty:
        raise ValueError(f"Research universe file contains no rows: {path}")

    validate_universe(universe)
    universe = universe.copy()
    universe["ticker"] = _clean_text(universe["ticker"]).str.upper()
    return universe


def validate_universe(df):
    """Validate the research-universe schema and categorical constraints."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Research universe must be a pandas DataFrame")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(
            "Research universe is missing required columns: "
            + ", ".join(missing_columns)
        )

    tickers = _clean_text(df["ticker"])
    if tickers.eq("").any():
        raise ValueError("Research universe contains an empty ticker")

    duplicate_mask = tickers.str.upper().duplicated(keep=False)
    if duplicate_mask.any():
        duplicates = sorted(tickers[duplicate_mask].str.upper().unique())
        raise ValueError(
            "Research universe contains duplicate ticker(s): " + ", ".join(duplicates)
        )

    statuses = _clean_text(df["status"])
    invalid_statuses = sorted(set(statuses) - ALLOWED_STATUSES)
    if invalid_statuses:
        raise ValueError(
            "Research universe contains invalid status value(s): "
            + ", ".join(value or "<empty>" for value in invalid_statuses)
        )

    layers = _clean_text(df["layer"])
    invalid_layers = sorted(set(layers) - ALLOWED_LAYERS)
    if invalid_layers:
        raise ValueError(
            "Research universe contains invalid layer value(s): "
            + ", ".join(value or "<empty>" for value in invalid_layers)
        )

    return True


def get_active_symbols(df):
    """Return research tickers whose saved status is ACTIVE, in source order."""
    validate_universe(df)
    tickers = _clean_text(df["ticker"])
    statuses = _clean_text(df["status"])
    return tickers.str.upper()[statuses.eq("ACTIVE")].tolist()


def get_primary_tickers(df=None):
    """Return every configured primary-universe ticker in source order."""
    universe = load_universe() if df is None else df
    validate_universe(universe)
    return _clean_text(universe["ticker"]).str.upper().tolist()


def get_summary(df):
    """Return deterministic total, active, and layer counts."""
    validate_universe(df)
    statuses = _clean_text(df["status"])
    layers = _clean_text(df["layer"])
    layer_counts = layers.value_counts().to_dict()
    return {
        "total": int(len(df)),
        "active": int(statuses.eq("ACTIVE").sum()),
        "layer": {
            layer: int(layer_counts.get(layer, 0)) for layer in ("A", "B", "C")
        },
    }


def main():
    try:
        universe = load_universe()
        summary = get_summary(universe)
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Research universe error: {error}", file=sys.stderr)
        return 1

    print("AI_investing Research Universe")
    print()
    print("Total:")
    print(summary["total"])
    print()
    print("Active:")
    print(summary["active"])
    print()
    print("Layer:")
    print()
    for layer in ("A", "B", "C"):
        print(f"{layer}:")
        print(summary["layer"][layer])
        if layer != "C":
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
