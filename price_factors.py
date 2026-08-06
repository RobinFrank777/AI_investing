"""Pure native price-factor calculations.

All outputs are unrounded Python floats in decimal units. Invalid Close
observations are removed without filling. If every usable Close observation
has a valid Date, observations are stably sorted by Date; duplicate dates are
retained in their original relative order and count as separate observations.
"""

import math

import pandas as pd


TREND_OBSERVATIONS = 60
MOMENTUM_OBSERVATIONS = 21
VOLATILITY_OBSERVATIONS = 21


def _normalized_close(data):
    if not isinstance(data, pd.DataFrame):
        raise ValueError("price factor input must be a pandas DataFrame")
    if "Close" not in data.columns:
        raise ValueError("price factor input requires a Close column")

    working = data.copy(deep=True)
    working["Close"] = pd.to_numeric(working["Close"], errors="coerce")
    working = working[
        working["Close"].map(lambda value: pd.notna(value) and math.isfinite(value))
    ]
    if "Date" in working.columns and not working.empty:
        parsed_dates = pd.to_datetime(working["Date"], errors="coerce")
        if parsed_dates.notna().all():
            working = working.assign(_FactorDate=parsed_dates).sort_values(
                "_FactorDate", kind="mergesort"
            )
    return working["Close"].reset_index(drop=True)


def _finite_float(value):
    result = float(value)
    return result if math.isfinite(result) else None


def calculate_trend_value(data):
    """Return latest Close / trailing 60-observation mean - 1."""
    close = _normalized_close(data)
    if len(close) < TREND_OBSERVATIONS:
        return None
    window = close.iloc[-TREND_OBSERVATIONS:]
    mean = window.mean()
    if mean == 0:
        return None
    return _finite_float(window.iloc[-1] / mean - 1)


def calculate_momentum_value(data):
    """Return Close[t] / Close[t-20] - 1, requiring 21 observations."""
    close = _normalized_close(data)
    if len(close) < MOMENTUM_OBSERVATIONS:
        return None
    base = close.iloc[-MOMENTUM_OBSERVATIONS]
    if base == 0:
        return None
    return _finite_float(close.iloc[-1] / base - 1)


def calculate_volatility_20d(data):
    """Return sample std (ddof=1) of the latest 20 daily decimal returns."""
    close = _normalized_close(data)
    if len(close) < VOLATILITY_OBSERVATIONS:
        return None
    returns = close.iloc[-VOLATILITY_OBSERVATIONS:].pct_change().iloc[1:]
    returns = returns[returns.map(lambda value: math.isfinite(value))]
    if len(returns) != 20:
        return None
    return _finite_float(returns.std(ddof=1))


def calculate_price_factors(data):
    """Return all native factors with a fixed key order."""
    return {
        "TrendValue": calculate_trend_value(data),
        "MomentumValue": calculate_momentum_value(data),
        "Volatility20D": calculate_volatility_20d(data),
    }
