"""Run native price factors across ACTIVE Universe150 research symbols."""

import sys
from pathlib import Path

import pandas as pd

import factor_engine
import universe_loader


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_factor_raw.csv"
RAW_FACTOR_COLUMNS = (
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
    "FactorStatus",
    "FactorError",
)
NATIVE_FACTOR_COLUMNS = tuple(factor_engine.FACTOR_ENGINE_COLUMNS[1:])


def _failed_row(ticker, error):
    return {
        "Ticker": ticker,
        "TrendValue": None,
        "MomentumValue": None,
        "Volatility20D": None,
        "FactorStatus": "FAILED",
        "FactorError": f"{type(error).__name__}: {error}",
    }


def _successful_row(ticker, factors):
    if not isinstance(factors, pd.DataFrame) or len(factors) != 1:
        raise ValueError("factor engine must return a single-row DataFrame")
    missing = [column for column in factor_engine.FACTOR_ENGINE_COLUMNS if column not in factors]
    if missing:
        raise ValueError(
            "factor engine result is missing columns: " + ", ".join(missing)
        )

    source = factors.iloc[0]
    values = {column: source[column] for column in NATIVE_FACTOR_COLUMNS}
    missing_factors = [column for column, value in values.items() if pd.isna(value)]
    return {
        "Ticker": ticker,
        **values,
        "FactorStatus": "PASS" if not missing_factors else "PARTIAL",
        "FactorError": (
            "Missing factor values: " + ", ".join(missing_factors)
            if missing_factors
            else ""
        ),
    }


def build_universe_factor_table(universe_path=None, data_dir=None):
    """Calculate raw factors for ACTIVE research symbols with failure isolation."""
    universe = universe_loader.load_universe(universe_path)
    symbols = universe_loader.get_active_symbols(universe)
    root = DEFAULT_DATA_DIR if data_dir is None else Path(data_dir)
    rows = []
    for ticker in symbols:
        try:
            factors = factor_engine.calculate_factors(
                root / f"{ticker}.csv", ticker=ticker
            )
            row = _successful_row(ticker, factors)
        except Exception as error:
            row = _failed_row(ticker, error)
        rows.append(row)
    return pd.DataFrame(rows, columns=RAW_FACTOR_COLUMNS)


def save_universe_factor_table(factors, output_path=None):
    """Save an already-built raw research factor table without an index."""
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    factors.to_csv(path, index=False)
    return path


def run_universe_factors(universe_path=None, data_dir=None, output_path=None):
    """Build and save the Universe150 raw factor artifact."""
    factors = build_universe_factor_table(universe_path, data_dir)
    path = save_universe_factor_table(factors, output_path)
    status_counts = factors["FactorStatus"].value_counts().to_dict()
    return {
        "factors": factors,
        "output_path": str(path),
        "summary": {
            "total": int(len(factors)),
            "pass": int(status_counts.get("PASS", 0)),
            "partial": int(status_counts.get("PARTIAL", 0)),
            "failed": int(status_counts.get("FAILED", 0)),
        },
    }


def main():
    try:
        result = run_universe_factors()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 factor runner error: {error}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("AI_investing Universe150 Raw Factors")
    print(f"Total: {summary['total']}")
    print(f"PASS: {summary['pass']}")
    print(f"PARTIAL: {summary['partial']}")
    print(f"FAILED: {summary['failed']}")
    print(f"Output: {result['output_path']}")
    print("Research factors only; no ranking, normalization, or trading action was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
