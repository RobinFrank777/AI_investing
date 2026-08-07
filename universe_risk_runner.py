"""Run single-ticker risk metrics across ACTIVE Universe150 symbols."""

import sys
from pathlib import Path

import pandas as pd

import risk_engine
import universe_loader


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_risk_raw.csv"
OUTPUT_COLUMNS = (
    "Ticker",
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
    "ObservationCount",
    "Status",
)
METRIC_COLUMNS = ("AnnualizedVolatility", "MaxDrawdown", "SharpeRatio")


def _observation_count(path):
    try:
        return int(len(pd.read_csv(path)))
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return 0


def _failed_row(ticker, observation_count=0):
    return {
        "Ticker": ticker,
        "AnnualizedVolatility": None,
        "MaxDrawdown": None,
        "SharpeRatio": None,
        "ObservationCount": int(observation_count),
        "Status": "FAILED",
    }


def _runner_row(ticker, risk, observation_count):
    if not isinstance(risk, pd.DataFrame) or len(risk) != 1:
        raise ValueError("risk engine must return a single-row DataFrame")
    required = {"Ticker", *METRIC_COLUMNS, "RiskStatus"}
    missing = sorted(required - set(risk.columns))
    if missing:
        raise ValueError("risk engine result is missing columns: " + ", ".join(missing))

    source = risk.iloc[0]
    engine_status = str(source["RiskStatus"])
    if engine_status == "FAILED":
        return _failed_row(ticker, observation_count)
    metrics = {column: source[column] for column in METRIC_COLUMNS}
    missing_metrics = any(pd.isna(value) for value in metrics.values())
    return {
        "Ticker": ticker,
        **metrics,
        "ObservationCount": int(observation_count),
        "Status": "PARTIAL" if missing_metrics or engine_status == "PARTIAL" else "PASS",
    }


def build_universe_risk_table(universe_path=None, data_dir=None):
    """Calculate risk rows for ACTIVE symbols while isolating ticker failures."""
    universe = universe_loader.load_universe(universe_path)
    symbols = universe_loader.get_active_symbols(universe)
    root = DEFAULT_DATA_DIR if data_dir is None else Path(data_dir)
    rows = []
    for ticker in symbols:
        path = root / f"{ticker}.csv"
        count = _observation_count(path)
        try:
            risk = risk_engine.calculate_risk(path, ticker=ticker)
            row = _runner_row(ticker, risk, count)
        except Exception:
            row = _failed_row(ticker, count)
        rows.append(row)
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def save_universe_risk_table(risk, output_path=None):
    """Save an already-built Universe150 risk table without an index."""
    if not isinstance(risk, pd.DataFrame):
        raise TypeError("risk must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    risk.to_csv(path, index=False)
    return path


def run_universe_risk(universe_path=None, data_dir=None, output_path=None):
    """Build and save the Universe150 raw risk artifact."""
    risk = build_universe_risk_table(universe_path, data_dir)
    path = save_universe_risk_table(risk, output_path)
    counts = risk["Status"].value_counts().to_dict()
    return {
        "risk": risk,
        "output_path": str(path),
        "summary": {
            "total": int(len(risk)),
            "pass": int(counts.get("PASS", 0)),
            "partial": int(counts.get("PARTIAL", 0)),
            "failed": int(counts.get("FAILED", 0)),
        },
    }


def main():
    try:
        result = run_universe_risk()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 risk runner error: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print("AI_investing Universe150 Raw Risk")
    print(f"Total: {summary['total']}")
    print(f"PASS: {summary['pass']}")
    print(f"PARTIAL: {summary['partial']}")
    print(f"FAILED: {summary['failed']}")
    print(f"Output: {result['output_path']}")
    print("Research risk metrics only; no execution workflow was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
