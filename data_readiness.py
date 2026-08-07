"""Research-only market-data readiness checks for the Universe150 universe."""

import sys
from pathlib import Path

import pandas as pd

from universe_loader import DEFAULT_UNIVERSE_PATH, get_active_symbols, load_universe


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_data_readiness.csv"
REQUIRED_PRICE_COLUMNS = ("Date", "Close", "High", "Low", "Open", "Volume")
MINIMUM_HISTORY_ROWS = 252
READINESS_COLUMNS = (
    "Ticker",
    "FilePath",
    "FileExists",
    "RequiredColumnsPresent",
    "MissingColumns",
    "HistoryRows",
    "MinimumHistoryRows",
    "HistorySufficient",
    "Ready",
    "Error",
)


def inspect_price_file(ticker, data_dir=None):
    """Return one readiness record without changing or downloading price data."""
    root = DEFAULT_DATA_DIR if data_dir is None else Path(data_dir)
    path = root / f"{ticker}.csv"
    record = {
        "Ticker": str(ticker),
        "FilePath": str(path),
        "FileExists": path.is_file(),
        "RequiredColumnsPresent": False,
        "MissingColumns": ",".join(REQUIRED_PRICE_COLUMNS),
        "HistoryRows": 0,
        "MinimumHistoryRows": MINIMUM_HISTORY_ROWS,
        "HistorySufficient": False,
        "Ready": False,
        "Error": "",
    }
    if not record["FileExists"]:
        record["Error"] = "Price file not found"
        return record

    try:
        prices = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        record["Error"] = "Price file is empty"
        return record
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        record["Error"] = f"Price file could not be read: {type(error).__name__}"
        return record

    missing = [column for column in REQUIRED_PRICE_COLUMNS if column not in prices.columns]
    history_rows = int(len(prices))
    columns_present = not missing
    history_sufficient = history_rows >= MINIMUM_HISTORY_ROWS
    record.update(
        {
            "RequiredColumnsPresent": columns_present,
            "MissingColumns": ",".join(missing),
            "HistoryRows": history_rows,
            "HistorySufficient": history_sufficient,
            "Ready": columns_present and history_sufficient,
        }
    )
    if missing:
        record["Error"] = "Missing required columns"
    elif not history_sufficient:
        record["Error"] = "Insufficient history"
    return record


def build_data_readiness(universe_path=None, data_dir=None):
    """Build readiness rows for ACTIVE research-universe symbols only."""
    universe = load_universe(
        DEFAULT_UNIVERSE_PATH if universe_path is None else universe_path
    )
    records = [
        inspect_price_file(ticker, data_dir=data_dir)
        for ticker in get_active_symbols(universe)
    ]
    return pd.DataFrame(records, columns=READINESS_COLUMNS)


def save_data_readiness(readiness, output_path=None):
    """Save an already-built readiness table to the research results directory."""
    if not isinstance(readiness, pd.DataFrame):
        raise TypeError("readiness must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    readiness.to_csv(path, index=False)
    return path


def run_data_readiness(universe_path=None, data_dir=None, output_path=None):
    """Build and save the Universe150 research data-readiness artifact."""
    readiness = build_data_readiness(universe_path=universe_path, data_dir=data_dir)
    path = save_data_readiness(readiness, output_path=output_path)
    return {"readiness": readiness, "output_path": str(path)}


def main():
    try:
        result = run_data_readiness()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 data readiness error: {error}", file=sys.stderr)
        return 1

    readiness = result["readiness"]
    ready_count = int(readiness["Ready"].sum()) if not readiness.empty else 0
    print("AI_investing Universe150 Data Readiness")
    print(f"Active symbols: {len(readiness)}")
    print(f"Ready: {ready_count}")
    print(f"Not ready: {len(readiness) - ready_count}")
    print(f"Output: {result['output_path']}")
    print("Research data check only; no production or trading action was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
