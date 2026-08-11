"""Audit Investment Profile coverage for the current stock universe."""

import sys
from pathlib import Path

import pandas as pd

from investment_profile_loader import load_company_profiles
from universe_loader import DEFAULT_UNIVERSE_PATH


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TIER_PATH = PROJECT_ROOT / "data" / "company_profile_tiers.csv"
TIER_COLUMNS = ("ticker", "tier", "priority", "reason")
VALID_TIERS = ("Tier1", "Tier2", "Tier3")


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


def _load_tier_data(tier_path, universe_tickers):
    path = Path(tier_path)
    if not path.is_file():
        raise FileNotFoundError(f"Investment Profile tier file not found: {path}")
    try:
        tiers = pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Investment Profile tier file is empty: {path}") from error
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Investment Profile tier file is invalid: {path}") from error

    if tuple(tiers.columns) != TIER_COLUMNS:
        raise ValueError(
            "Investment Profile tier schema must be: " + ", ".join(TIER_COLUMNS)
        )
    if tiers.empty:
        raise ValueError(f"Investment Profile tier file contains no records: {path}")

    normalized_tickers = tiers["ticker"].fillna("").astype(str).str.strip().str.upper()
    if normalized_tickers.eq("").any():
        raise ValueError("Investment Profile tier metadata contains an empty ticker")
    duplicate_tickers = normalized_tickers[normalized_tickers.duplicated(keep=False)]
    if not duplicate_tickers.empty:
        duplicates = ", ".join(dict.fromkeys(duplicate_tickers))
        raise ValueError(f"Duplicate Investment Profile tier ticker: {duplicates}")

    invalid_tiers = sorted(set(tiers["tier"].astype(str)) - set(VALID_TIERS))
    if invalid_tiers:
        raise ValueError("Unknown Investment Profile tier: " + ", ".join(invalid_tiers))

    outside_universe = sorted(set(normalized_tickers) - set(universe_tickers))
    if outside_universe:
        raise ValueError(
            "Investment Profile tier ticker not in Universe150: "
            + ", ".join(outside_universe)
        )

    tiers = tiers.copy()
    tiers["ticker"] = normalized_tickers
    return tiers


def _coverage_metrics(tickers, profile_tickers):
    missing_tickers = [ticker for ticker in tickers if ticker not in profile_tickers]
    total = len(tickers)
    missing = len(missing_tickers)
    covered = total - missing
    coverage_rate = round(covered / total * 100, 2) if total else 0.0
    return {
        "total": total,
        "covered": covered,
        "missing": missing,
        "coverage_rate": coverage_rate,
        "missing_tickers": missing_tickers,
    }


def check_profile_coverage(
    universe_path=DEFAULT_UNIVERSE_PATH,
    tier_path=DEFAULT_TIER_PATH,
):
    """Return unique-ticker Investment Profile coverage for a universe CSV."""
    universe_tickers = _load_universe_tickers(universe_path)
    tier_data = _load_tier_data(tier_path, universe_tickers)

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

    overall = _coverage_metrics(universe_tickers, profile_tickers)
    tier_results = {}
    for tier in VALID_TIERS:
        tier_tickers = tier_data.loc[tier_data["tier"].eq(tier), "ticker"].tolist()
        if tier_tickers:
            tier_results[tier] = _coverage_metrics(tier_tickers, profile_tickers)

    return {
        "universe_count": overall["total"],
        "profile_count": overall["covered"],
        "missing_count": overall["missing"],
        "coverage_rate": overall["coverage_rate"],
        "missing_tickers": overall["missing_tickers"],
        "tiers": tier_results,
    }


def main():
    try:
        result = check_profile_coverage()
    except (FileNotFoundError, ValueError, KeyError, OSError) as error:
        print(f"Investment Profile coverage error: {error}", file=sys.stderr)
        return 1

    print("INVESTMENT PROFILE COVERAGE")
    for tier, metrics in result["tiers"].items():
        print()
        print(tier)
        print(f"Total: {metrics['total']}")
        print(f"Covered: {metrics['covered']}")
        print(f"Missing: {metrics['missing']}")
        print(f"Coverage rate: {metrics['coverage_rate']:.2f}%")
        missing = ", ".join(metrics["missing_tickers"]) or "None"
        print(f"Missing tickers: {missing}")

    print()
    print("Universe150")
    print(f"Total: {result['universe_count']}")
    print(f"Covered: {result['profile_count']}")
    print(f"Missing: {result['missing_count']}")
    print(f"Coverage rate: {result['coverage_rate']:.2f}%")
    overall_missing = ", ".join(result["missing_tickers"]) or "None"
    print(f"Missing tickers: {overall_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
