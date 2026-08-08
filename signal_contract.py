"""Canonical semantic mappings for research signal fields."""


TREND_SIGNAL_MAP = {
    "STRONG": "BULLISH",
    "NORMAL": "NEUTRAL",
    "WEAK": "BEARISH",
    "UNKNOWN": "UNKNOWN",
}
MOMENTUM_SIGNAL_MAP = {
    "POSITIVE": "STRONG",
    "NEUTRAL": "NORMAL",
    "NEGATIVE": "WEAK",
    "UNKNOWN": "UNKNOWN",
}
VOLATILITY_SIGNALS = frozenset({"LOW", "NORMAL", "HIGH", "UNKNOWN"})


def _normalized(value):
    return "" if value is None else str(value).strip().upper()


def normalize_trend_signal(value):
    """Map a raw trend state to its research semantic state."""
    return TREND_SIGNAL_MAP.get(_normalized(value), "UNKNOWN")


def normalize_momentum_signal(value):
    """Map a raw momentum state to its research semantic state."""
    return MOMENTUM_SIGNAL_MAP.get(_normalized(value), "UNKNOWN")


def normalize_volatility_signal(value):
    """Normalize a volatility state without changing its meaning."""
    normalized = _normalized(value)
    return normalized if normalized in VOLATILITY_SIGNALS else "UNKNOWN"
