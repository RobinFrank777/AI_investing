"""Compatibility exports for canonical research dataset fields."""

from src.research.research_schema import (
    FIELD_ALIASES,
    STANDARD_FIELDS,
    normalize_research_schema,
    validate_research_schema,
)


__all__ = [
    "STANDARD_FIELDS",
    "FIELD_ALIASES",
    "normalize_research_schema",
    "validate_research_schema",
]
