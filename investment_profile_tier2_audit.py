"""Audit Tier2 Investment Profile coverage and research priority."""

import sys
from pathlib import Path

import pandas as pd

import investment_profile_coverage as coverage
from universe_loader import DEFAULT_UNIVERSE_PATH


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TIER_PATH = PROJECT_ROOT / "data" / "company_profile_tiers.csv"

PRIORITY_B_THEMES = {
    "AI-enabled consumer platform",
    "Healthcare services / digital health",
    "Medicines / biotechnology",
}
PRIORITY_C_THEMES = {
    "Early-stage biotechnology",
    "Quantum computing",
}


def _classify_priority(row):
    """Classify a missing Tier2 company by strategic research relevance."""
    theme = str(row["theme"]).strip()
    ticker = str(row["ticker"]).strip().upper()
    if theme in PRIORITY_C_THEMES:
        return "C"
    if theme in PRIORITY_B_THEMES or ticker == "OKTA":
        return "B"
    return "A"


def audit_tier2_coverage(
    universe_path=DEFAULT_UNIVERSE_PATH,
    tier_path=DEFAULT_TIER_PATH,
):
    """Return Tier2 coverage details and priorities for missing profiles."""
    result = coverage.check_profile_coverage(universe_path, tier_path)
    tier_metrics = result["tiers"].get(
        "Tier2",
        {
            "total": 0,
            "covered": 0,
            "missing": 0,
            "coverage_rate": 0.0,
            "missing_tickers": [],
        },
    )

    tiers = pd.read_csv(tier_path)
    universe = pd.read_csv(universe_path)
    tier2 = tiers.loc[tiers["tier"].eq("Tier2"), ["ticker", "reason"]].copy()
    tier2["ticker"] = tier2["ticker"].astype(str).str.strip().str.upper()

    universe_fields = universe.loc[
        :, ["ticker", "company", "sector", "industry", "theme"]
    ].copy()
    universe_fields["ticker"] = (
        universe_fields["ticker"].astype(str).str.strip().str.upper()
    )
    details = tier2.merge(universe_fields, on="ticker", how="left", validate="one_to_one")

    missing_tickers = set(tier_metrics["missing_tickers"])
    covered = details.loc[
        ~details["ticker"].isin(missing_tickers), ["ticker", "company"]
    ].to_dict("records")
    missing = details.loc[
        details["ticker"].isin(missing_tickers),
        ["ticker", "company", "sector", "industry", "reason", "theme"],
    ].copy()
    missing["priority"] = missing.apply(_classify_priority, axis=1)

    priority_lists = {
        priority: missing.loc[missing["priority"].eq(priority), "ticker"].tolist()
        for priority in ("A", "B", "C")
    }
    missing_records = missing.drop(columns=["theme"]).to_dict("records")

    return {
        "total": tier_metrics["total"],
        "existing": tier_metrics["covered"],
        "missing_count": tier_metrics["missing"],
        "coverage_rate": tier_metrics["coverage_rate"],
        "covered": covered,
        "missing": missing_records,
        "priorities": priority_lists,
    }


def _print_table(headers, rows):
    print(" | ".join(headers))
    for row in rows:
        print(" | ".join(str(row[header]) for header in headers))


def main():
    try:
        result = audit_tier2_coverage()
    except (FileNotFoundError, ValueError, KeyError, OSError, pd.errors.ParserError) as error:
        print(f"Tier2 audit error: {error}", file=sys.stderr)
        return 1

    print("TIER2 COVERAGE AUDIT")
    print()
    print(f"Total Tier2: {result['total']}")
    print(f"Existing profiles: {result['existing']}")
    print(f"Missing: {result['missing_count']}")
    print(f"Coverage: {result['coverage_rate']:.2f}%")

    print()
    print("COVERED TIER2")
    if result["covered"]:
        _print_table(["ticker", "company"], result["covered"])
    else:
        print("None")

    print()
    print("MISSING TIER2")
    if result["missing"]:
        _print_table(
            ["ticker", "company", "sector", "industry", "reason", "priority"],
            result["missing"],
        )
    else:
        print("None")

    for priority in ("A", "B", "C"):
        print()
        print(f"PRIORITY {priority}")
        tickers = result["priorities"][priority]
        print(", ".join(tickers) if tickers else "None")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
