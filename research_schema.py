"""Canonical field compatibility helpers for research datasets."""

import pandas as pd


STANDARD_FIELDS = ("Ticker", "Signal")
FIELD_ALIASES = {
    "Ticker": "Symbol",
    "Signal": "CompositeSignal",
}


def _missing_text(series):
    return series.isna() | series.astype(str).str.strip().eq("")


def normalize_research_schema(df):
    """Return a non-destructive copy containing canonical research fields."""
    if df is None:
        return pd.DataFrame(columns=STANDARD_FIELDS)
    if not isinstance(df, pd.DataFrame):
        raise TypeError("research data must be a pandas DataFrame or None")

    result = df.copy(deep=True)
    if result.empty and len(result.columns) == 0:
        return pd.DataFrame(columns=STANDARD_FIELDS, index=result.index)

    missing_sources = []
    for canonical, alias in FIELD_ALIASES.items():
        has_canonical = canonical in result.columns
        has_alias = alias in result.columns
        if not has_canonical and not has_alias:
            if result.empty:
                result[canonical] = pd.Series(index=result.index, dtype="object")
            else:
                missing_sources.append(f"{canonical} (or {alias})")
            continue
        if not has_canonical:
            result[canonical] = result[alias].copy()
        elif has_alias:
            missing = _missing_text(result[canonical])
            result.loc[missing, canonical] = result.loc[missing, alias]

    if missing_sources:
        raise ValueError(
            "research data is missing required fields: " + ", ".join(missing_sources)
        )
    validate_research_schema(result)
    return result


def validate_research_schema(df):
    """Return True when both canonical research fields are present."""
    if df is None:
        raise ValueError("research data is required")
    if not isinstance(df, pd.DataFrame):
        raise TypeError("research data must be a pandas DataFrame")
    missing = [field for field in STANDARD_FIELDS if field not in df.columns]
    if missing:
        raise ValueError(
            "research data is missing standard fields: " + ", ".join(missing)
        )
    return True
