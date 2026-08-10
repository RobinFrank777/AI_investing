"""Validate the Company Profile master data contract."""

from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FILEPATH = PROJECT_ROOT / "data" / "company_profile.csv"
EXPECTED_COLUMNS = (
    "ticker",
    "company",
    "sector",
    "industry",
    "country",
    "business_model",
    "investment_thesis",
    "moat_score",
    "valuation_type",
    "growth_driver",
    "risk_factor",
    "investment_stage",
    "investor_rating",
    "last_update",
)
ALLOWED_VALUATION_TYPES = frozenset(
    {"Growth", "Value", "Cyclical", "Asset-Based", "Not Applicable"}
)
ALLOWED_INVESTMENT_STAGES = frozenset(
    {"MATURE", "GROWTH", "EARLY_GROWTH", "SPECULATIVE", "CYCLICAL"}
)
CHECK_LABELS = (
    "14-column schema",
    "no missing values",
    "ticker unique",
    "moat_score valid",
    "investor_rating valid",
    "valuation_type valid",
    "investment_stage valid",
    "last_update valid",
)


def _result(companies, errors, checks=None):
    return {
        "status": "FAIL" if errors else "PASS",
        "companies": int(companies),
        "errors": errors,
        "checks": checks or [],
    }


def _valid_date(value):
    text = str(value)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%d") == text


def validate_company_profile(filepath="data/company_profile.csv"):
    """Validate Company Profile master data and return a structured result."""
    path = Path(filepath)
    if filepath == "data/company_profile.csv":
        path = DEFAULT_FILEPATH

    if not path.is_file():
        return _result(0, [f"file not found: {path}"])

    try:
        data = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return _result(0, ["empty CSV"])
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        return _result(0, [f"CSV parse failed: {error}"])

    companies = len(data)
    errors = []
    checks = []
    actual_columns = tuple(data.columns)
    if actual_columns != EXPECTED_COLUMNS:
        missing = [column for column in EXPECTED_COLUMNS if column not in actual_columns]
        extra = [column for column in actual_columns if column not in EXPECTED_COLUMNS]
        if missing:
            errors.append(f"missing columns: {', '.join(missing)}")
        if extra:
            errors.append(f"extra columns: {', '.join(extra)}")
        if not missing and not extra:
            errors.append("column order invalid")
        return _result(companies, errors, checks)
    checks.append(CHECK_LABELS[0])

    if data.empty:
        errors.append("empty CSV")

    missing_mask = data.isna() | data.apply(
        lambda column: column.map(lambda value: isinstance(value, str) and not value.strip())
    )
    if missing_mask.to_numpy().any():
        errors.append("missing values")
    else:
        checks.append(CHECK_LABELS[1])

    ticker = data["ticker"]
    duplicates = ticker[ticker.duplicated(keep=False) & ticker.notna()].astype(str).unique()
    if len(duplicates):
        errors.extend(f"duplicate ticker: {ticker_value}" for ticker_value in duplicates)
    else:
        checks.append(CHECK_LABELS[2])

    numeric_rules = (("moat_score", 0, 5), ("investor_rating", 0, 100))
    for column, minimum, maximum in numeric_rules:
        numeric = pd.to_numeric(data[column], errors="coerce")
        if (
            numeric.isna().any()
            or not numeric.between(minimum, maximum).all()
            or not numeric.mod(1).eq(0).all()
        ):
            errors.append(f"{column} invalid")
        else:
            checks.append(f"{column} valid")

    if data["valuation_type"].isin(ALLOWED_VALUATION_TYPES).all():
        checks.append(CHECK_LABELS[5])
    else:
        errors.append("valuation_type invalid")

    if data["investment_stage"].isin(ALLOWED_INVESTMENT_STAGES).all():
        checks.append(CHECK_LABELS[6])
    else:
        errors.append("investment_stage invalid")

    if data["last_update"].map(_valid_date).all():
        checks.append(CHECK_LABELS[7])
    else:
        errors.append("last_update invalid")

    return _result(companies, errors, checks)


def main():
    result = validate_company_profile()
    for check in result["checks"]:
        print(f"PASS: {check}")
    print()
    print("=" * 50)
    print(f"COMPANY PROFILE VALIDATION: {result['status']}")
    print(f"Companies: {result['companies']}")
    print(f"Errors: {len(result['errors'])}")
    for error in result["errors"]:
        print(f"ERROR: {error}")
    print("=" * 50)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
