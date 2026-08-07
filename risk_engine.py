"""Single-ticker historical risk metrics for the research workflow."""

import math
from pathlib import Path

import pandas as pd


TRADING_DAYS_PER_YEAR = 252
RISK_COLUMNS = (
    "Ticker",
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
    "RiskStatus",
    "RiskError",
)


def _empty_row(ticker, status, error):
    return {
        "Ticker": ticker,
        "AnnualizedVolatility": None,
        "MaxDrawdown": None,
        "SharpeRatio": None,
        "RiskStatus": status,
        "RiskError": error,
    }


def _finite(value):
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _load_history(path):
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
    if "Close" not in history:
        raise ValueError("Historical price CSV requires a Close column")
    return history


def _clean_close(history):
    working = history.copy(deep=True)
    working["Close"] = pd.to_numeric(working["Close"], errors="coerce")
    valid_close = working["Close"].map(
        lambda value: pd.notna(value) and math.isfinite(value) and value > 0
    )
    working = working.loc[valid_close]
    if working.empty:
        raise ValueError("Historical price CSV contains no valid positive Close values")
    if "Date" in working:
        parsed_dates = pd.to_datetime(working["Date"], errors="coerce")
        if parsed_dates.notna().all():
            working = working.assign(_RiskDate=parsed_dates).sort_values(
                "_RiskDate", kind="mergesort"
            )
    return working["Close"].reset_index(drop=True)


def calculate_risk_metrics(input_path, ticker=None):
    """Return one fixed-schema risk row; invalid inputs become FAILED rows."""
    try:
        path = Path(input_path)
        selected_ticker = path.stem if ticker is None else str(ticker).strip()
        if not selected_ticker:
            raise ValueError("ticker must not be empty")
        history = _load_history(path)
        close = _clean_close(history)
        returns = close.pct_change(fill_method=None).iloc[1:]
        returns = returns[
            returns.map(lambda value: pd.notna(value) and math.isfinite(value))
        ]

        drawdown = close / close.cummax() - 1.0
        max_drawdown = _finite(drawdown.min())
        annualized_volatility = None
        sharpe_ratio = None
        if len(returns) >= 2:
            daily_volatility = _finite(returns.std(ddof=1))
            if daily_volatility is not None:
                annualized_volatility = daily_volatility * math.sqrt(
                    TRADING_DAYS_PER_YEAR
                )
                if daily_volatility > 0:
                    sharpe_ratio = (
                        _finite(returns.mean())
                        / daily_volatility
                        * math.sqrt(TRADING_DAYS_PER_YEAR)
                    )

        metrics = {
            "AnnualizedVolatility": annualized_volatility,
            "MaxDrawdown": max_drawdown,
            "SharpeRatio": sharpe_ratio,
        }
        missing = [name for name, value in metrics.items() if value is None]
        row = {
            "Ticker": selected_ticker,
            **metrics,
            "RiskStatus": "PASS" if not missing else "PARTIAL",
            "RiskError": (
                "Unavailable metrics: " + ", ".join(missing) if missing else ""
            ),
        }
    except Exception as error:
        fallback_ticker = ""
        if ticker is not None:
            fallback_ticker = str(ticker).strip()
        elif input_path is not None:
            try:
                fallback_ticker = Path(input_path).stem
            except (TypeError, ValueError):
                fallback_ticker = ""
        row = _empty_row(
            fallback_ticker, "FAILED", f"{type(error).__name__}: {error}"
        )
    return pd.DataFrame([row], columns=RISK_COLUMNS)


def calculate_risk(input_path, ticker=None):
    """Public Phase 9G API for one ticker; delegates to the metric engine."""
    return calculate_risk_metrics(input_path, ticker=ticker)
