"""Compatibility exports for native price-factor calculations."""

from src.research.technical.price_factors import (
    MOMENTUM_OBSERVATIONS,
    TREND_OBSERVATIONS,
    VOLATILITY_OBSERVATIONS,
    calculate_momentum_value,
    calculate_price_factors,
    calculate_trend_value,
    calculate_volatility_20d,
)


__all__ = [
    "TREND_OBSERVATIONS",
    "MOMENTUM_OBSERVATIONS",
    "VOLATILITY_OBSERVATIONS",
    "calculate_trend_value",
    "calculate_momentum_value",
    "calculate_volatility_20d",
    "calculate_price_factors",
]
