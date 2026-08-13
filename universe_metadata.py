"""Small UniverseVersion metadata contract for universe-sensitive artifacts."""

from __future__ import annotations

import pandas as pd

from config import PRIMARY_UNIVERSE_VERSION


UNIVERSE_VERSION_FIELD = "UniverseVersion"
MATCH = "MATCH"
MISMATCH = "MISMATCH"
MISSING = "MISSING"


def universe_compatibility(value) -> str:
    """Classify an artifact UniverseVersion against the current authority."""
    if value is None or pd.isna(value) or not str(value).strip():
        return MISSING
    if str(value).strip() == PRIMARY_UNIVERSE_VERSION:
        return MATCH
    return MISMATCH


def tag_current_universe(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a tagged copy without changing membership or existing values."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("artifact must be a pandas DataFrame")
    tagged = frame.copy()
    tagged[UNIVERSE_VERSION_FIELD] = PRIMARY_UNIVERSE_VERSION
    return tagged


def dataframe_universe_compatibility(frame: pd.DataFrame) -> str:
    """Classify a tabular artifact; mixed explicit versions are mismatches."""
    if UNIVERSE_VERSION_FIELD not in frame.columns or frame.empty:
        return MISSING
    values = frame[UNIVERSE_VERSION_FIELD]
    states = {universe_compatibility(value) for value in values}
    return MATCH if states == {MATCH} else MISMATCH if MISMATCH in states or len(states) > 1 else MISSING
