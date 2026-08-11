"""Audit Investment Profile coverage for the current stock universe."""

import sys
from pathlib import Path

import pandas as pd

from investment_profile_loader import load_company_profiles
from universe_loader import DEFAULT_UNIVERSE_PATH


def _unique_tickers(values):
    tickers = []
    seen = set()
    for value in values:
        ticker = str(value).strip().upper() if pd.notna(value) else ""
        if not ticker:
            raise ValueError("Stock universe contains an empty ticker")
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def _load_universe_tickers(universe_path):
    path = Path(universe_path)
    if not path.is_file():
        raise FileNotFoundError(f"Stock universe file not found: {path}")
    try:
        universe = pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Stock universe file is empty: {path}") from error
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Stock universe file is invalid: {path}") from error
    if "ticker" not in universe.columns:
        raise ValueError("Stock universe is missing required column: ticker")
    return _unique_tickers(universe["ticker"])


def check_profile_coverage(universe_path=DEFAULT_UNIVERSE_PATH):
    """Return unique-ticker Investment Profile coverage for a universe CSV."""
    universe_tickers = _load_universe_tickers(universe_path)

    try:
        profiles = load_company_profiles()
    except ValueError as error:
        if "empty" not in str(error).lower():
            raise
        profile_tickers = set()
    else:
        profile_tickers = (
            set()
            if profiles.empty
            else set(_unique_tickers(profiles["ticker"]))
        )

    missing_tickers = [
        ticker for ticker in universe_tickers if ticker not in profile_tickers
    ]
    universe_count = len(universe_tickers)
    missing_count = len(missing_tickers)
    profile_count = universe_count - missing_count
    coverage_rate = (
        round(profile_count / universe_count * 100, 2) if universe_count else 0.0
    )
    return {
        "universe_count": universe_count,
        "profile_count": profile_count,
        "missing_count": missing_count,
        "coverage_rate": coverage_rate,
        "missing_tickers": missing_tickers,
    }


def main():
    try:
        result = check_profile_coverage()
    except (FileNotFoundError, ValueError, KeyError, OSError) as error:
        print(f"Investment Profile coverage error: {error}", file=sys.stderr)
        return 1

    print("INVESTMENT PROFILE COVERAGE")
    print(f"Universe count: {result['universe_count']}")
    print(f"Available profiles: {result['profile_count']}")
    print(f"Missing profiles: {result['missing_count']}")
    print(f"Coverage rate: {result['coverage_rate']:.2f}%")
    missing = ", ".join(result["missing_tickers"]) or "None"
    print(f"Missing tickers: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
