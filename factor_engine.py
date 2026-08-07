"""Single-ticker research factor engine using the existing price formulas."""

from pathlib import Path

import pandas as pd

from price_factors import calculate_price_factors


FACTOR_ENGINE_COLUMNS = (
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
)


def load_price_history(input_path):
    """Load one historical price CSV without applying universe-level behavior."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Historical price CSV not found: {path}")
    try:
        history = pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Historical price CSV is empty: {path}") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"Historical price CSV is invalid: {path}") from error
    if history.empty:
        raise ValueError(f"Historical price CSV contains no rows: {path}")
    return history


def calculate_factors(input_path, ticker=None):
    """Calculate native Trend, Momentum, and Low-Volatility inputs for one ticker."""
    path = Path(input_path)
    selected_ticker = path.stem if ticker is None else str(ticker).strip()
    if not selected_ticker:
        raise ValueError("ticker must not be empty")

    history = load_price_history(path)
    factors = calculate_price_factors(history)
    row = {
        "Ticker": selected_ticker,
        "TrendValue": factors["TrendValue"],
        "MomentumValue": factors["MomentumValue"],
        "Volatility20D": factors["Volatility20D"],
    }
    return pd.DataFrame([row], columns=FACTOR_ENGINE_COLUMNS)
