"""Audit remaining Tier2 Investment Profiles and research priority."""

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
    "Life-science tools / robotic surgery",
    "Medicines / biotechnology",
}
PRIORITY_C_THEMES = {
    "Early-stage biotechnology",
    "Quantum computing",
}

NEXT_BATCH_PREFERENCE = (
    "SKHY",
    "ZETA",
    "CSCO",
    "SNDK",
    "AMBA",
    "TXN",
    "NXPI",
    "AAOI",
    "NBIS",
    "CRWV",
    "NOC",
    "AVAV",
)


def _classify_priority(row):
    """Classify a missing Tier2 company by strategic research relevance."""
    theme = str(row["theme"]).strip()
    ticker = str(row["ticker"]).strip().upper()
    if theme in PRIORITY_C_THEMES:
        return "C"
    if theme in PRIORITY_B_THEMES or ticker == "OKTA":
        return "B"
    return "A"


def audit_remaining_tier2(
    universe_path=DEFAULT_UNIVERSE_PATH,
    tier_path=DEFAULT_TIER_PATH,
):
    """Return remaining Tier2 coverage, priorities, and next-batch candidates."""
    coverage_result = coverage.check_profile_coverage(universe_path, tier_path)
    tier_metrics = coverage_result["tiers"].get(
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
    existing = details.loc[
        ~details["ticker"].isin(missing_tickers), ["ticker", "company"]
    ].to_dict("records")
    missing = details.loc[
        details["ticker"].isin(missing_tickers),
        ["ticker", "company", "sector", "industry", "reason", "theme"],
    ].copy()
    missing["priority"] = missing.apply(_classify_priority, axis=1)

    priorities = {
        priority: missing.loc[missing["priority"].eq(priority), "ticker"].tolist()
        for priority in ("A", "B", "C")
    }
    missing_by_ticker = missing.set_index("ticker")
    recommended = []
    for ticker in NEXT_BATCH_PREFERENCE:
        if ticker not in priorities["A"]:
            continue
        row = missing_by_ticker.loc[ticker]
        recommended.append(
            {
                "ticker": ticker,
                "company": row["company"],
                "reason": row["reason"],
            }
        )

    return {
        "total": tier_metrics["total"],
        "existing_count": tier_metrics["covered"],
        "missing_count": tier_metrics["missing"],
        "coverage_rate": tier_metrics["coverage_rate"],
        "existing": existing,
        "missing": missing.drop(columns=["theme"]).to_dict("records"),
        "priorities": priorities,
        "recommended_next_batch": recommended,
    }


def _print_table(headers, rows):
    print(" | ".join(headers))
    for row in rows:
        print(" | ".join(str(row[header]) for header in headers))


def main():
    try:
        result = audit_remaining_tier2()
    except (FileNotFoundError, ValueError, KeyError, OSError, pd.errors.ParserError) as error:
        print(f"Tier2 remaining audit error: {error}", file=sys.stderr)
        return 1

    print("TIER2 REMAINING AUDIT")
    print()
    print(f"Total Tier2: {result['total']}")
    print(f"Existing: {result['existing_count']}")
    print(f"Missing: {result['missing_count']}")
    print(f"Coverage: {result['coverage_rate']:.2f}%")

    print()
    print("EXISTING TIER2 PROFILES")
    if result["existing"]:
        _print_table(["ticker", "company"], result["existing"])
    else:
        print("None")

    print()
    print("MISSING TIER2 PROFILES")
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

    print()
    print("RECOMMENDED NEXT BATCH")
    if result["recommended_next_batch"]:
        _print_table(
            ["ticker", "company", "reason"], result["recommended_next_batch"]
        )
    else:
        print("None")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
