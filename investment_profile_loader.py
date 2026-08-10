"""Load validated Company Profile master data for research modules."""

from pathlib import Path
from typing import Any

import pandas as pd

from company_profile_validator import (
    DEFAULT_FILEPATH,
    EXPECTED_COLUMNS,
    validate_company_profile,
)


def _resolve_path(filepath: str | Path) -> Path:
    if filepath == "data/company_profile.csv":
        return DEFAULT_FILEPATH
    return Path(filepath)


def load_company_profiles(
    filepath: str | Path = "data/company_profile.csv",
) -> pd.DataFrame:
    """Load and return the complete validated Company Profile dataset."""
    path = _resolve_path(filepath)
    validation = validate_company_profile(path)
    if validation["status"] != "PASS":
        if not path.is_file():
            raise FileNotFoundError(f"Company Profile file not found: {path}")
        details = "; ".join(validation["errors"])
        raise ValueError(f"Company Profile validation failed: {details}")

    return pd.read_csv(path, usecols=list(EXPECTED_COLUMNS))


def load_company_profile(
    ticker: str, filepath: str | Path = "data/company_profile.csv"
) -> dict[str, Any] | None:
    """Return one validated Company Profile, or None when ticker is unknown."""
    profiles = load_company_profiles(filepath)
    requested_ticker = str(ticker).strip().upper()
    ticker_values = profiles["ticker"].astype(str).str.strip().str.upper()
    matches = profiles.loc[ticker_values.eq(requested_ticker)]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()
