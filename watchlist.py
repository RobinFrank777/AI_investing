"""Legacy API name backed by the canonical primary-universe loader."""

from universe_loader import get_primary_tickers


def load_watchlist():
    """Return the primary universe; retained for caller API compatibility."""
    return get_primary_tickers()
