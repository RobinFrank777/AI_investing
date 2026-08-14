"""Build point-in-time production risk inputs from production candidates."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    HIGH_RISK_WEIGHT_MULTIPLIER,
    LOW_RISK_WEIGHT_MULTIPLIER,
    MEDIUM_RISK_WEIGHT_MULTIPLIER,
    PRIMARY_UNIVERSE_VERSION,
    UNKNOWN_RISK_WEIGHT_MULTIPLIER,
)
from portfolio_candidate_adapter import (
    DEFAULT_INPUT_PATH,
    build_validated_portfolio_candidates,
    load_production_candidates,
)
from stock_loader import load_stock


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "portfolio_risk_inputs.csv"
RISK_MODEL_VERSION = "risk-model-v3.8.2-p2"
REQUIRED_HISTORY_ROWS = 60
MAX_MARKET_STALENESS_DAYS = 5

RISK_INPUTS_READY = "RISK_INPUTS_READY"
NO_PORTFOLIO_ELIGIBLE_CANDIDATES = "NO_PORTFOLIO_ELIGIBLE_CANDIDATES"
NO_RISK_READY_CANDIDATES = "NO_RISK_READY_CANDIDATES"

CANDIDATE_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
    "CandidateRank", "FinalScore", "TradeSignal", "Eligibility",
    "PortfolioEligible",
)
OUTPUT_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
    "RiskModelVersion", "CandidateRank", "FinalScore", "TradeSignal",
    "Eligibility", "PortfolioEligible", "LatestClose", "LatestCloseAsOf",
    "MaxDrawdown", "SharpeRatio", "RiskLevel", "RiskWeightMultiplier",
    "RiskObservationCount", "ObservationEndDate", "Volatility20D",
    "Volatility60D", "ATR14", "ATRPercent", "AverageVolume20D",
    "AverageDollarVolume20D", "LiquidityCoverage", "CalculationTimestamp",
    "BacktestScore", "BacktestScoreSemantic", "AverageReturn", "WinRate",
    "RiskStatus", "RiskReadyForPortfolio", "RiskValidationReason",
)


class InsufficientHistoryError(LookupError):
    pass


class StaleHistoryError(LookupError):
    pass


def empty_risk_inputs(status=NO_PORTFOLIO_ELIGIBLE_CANDIDATES):
    result = pd.DataFrame(columns=OUTPUT_COLUMNS)
    result.attrs["RiskBuildStatus"] = status
    return result


def _single(frame, column):
    if frame[column].nunique(dropna=False) != 1:
        raise ValueError(f"validated candidates contain mixed {column}")


def _validate_candidates(candidates):
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    missing = [column for column in CANDIDATE_COLUMNS if column not in candidates]
    if missing:
        raise ValueError("validated candidates missing columns: " + ", ".join(missing))
    frame = candidates.loc[:, CANDIDATE_COLUMNS].copy(deep=True)
    if frame.empty:
        return frame
    for column in (
        "Ticker", "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
        "TradeSignal", "Eligibility",
    ):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if frame[column].eq("").any():
            raise ValueError(f"validated candidates contain missing {column}")
    frame["Ticker"] = frame.Ticker.str.upper()
    if frame.Ticker.duplicated().any():
        raise ValueError("validated candidates contain duplicate ticker")
    for column in ("RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion"):
        _single(frame, column)
    if frame.UniverseVersion.iloc[0] != PRIMARY_UNIVERSE_VERSION:
        raise ValueError("validated candidates contain incompatible UniverseVersion")
    frame["AsOfDate"] = pd.to_datetime(frame.AsOfDate, errors="raise").dt.date.astype(str)
    for column in ("CandidateRank", "FinalScore"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any() or not np.isfinite(frame[column]).all():
            raise ValueError(f"validated candidates contain non-finite {column}")
    eligible = frame.PortfolioEligible
    if eligible.dtype != bool:
        eligible = eligible.astype(str).str.upper().map({"TRUE": True, "FALSE": False})
    if eligible.isna().any():
        raise ValueError("validated candidates contain invalid PortfolioEligible")
    frame["PortfolioEligible"] = eligible.astype(bool)
    expected = frame.TradeSignal.str.upper().eq("BUY") & frame.Eligibility.str.upper().eq("ELIGIBLE")
    if not frame.PortfolioEligible.equals(expected):
        raise ValueError("PortfolioEligible conflicts with production eligibility contract")
    return frame


def _market_frame(ticker, market_data):
    return load_stock(ticker) if market_data is None else market_data[ticker].copy(deep=True)


def _calculate_market_risk(ticker, as_of_date, market_data):
    frame = _market_frame(ticker, market_data)
    required = {"Date", "High", "Low", "Close", "Volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("market data missing columns: " + ", ".join(missing))
    frame = frame.loc[:, ["Date", "High", "Low", "Close", "Volume"]].copy()
    frame["Date"] = pd.to_datetime(frame.Date, errors="coerce")
    if frame.Date.isna().any() or frame.Date.duplicated().any():
        raise ValueError("market data contains invalid or duplicate dates")
    cutoff = pd.Timestamp(as_of_date)
    frame = frame.loc[frame.Date <= cutoff].copy()
    for column in ("High", "Low", "Close", "Volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not np.isfinite(frame[["High", "Low", "Close", "Volume"]]).all().all():
        raise ValueError("market data contains non-finite values")
    frame = frame.sort_values("Date", kind="mergesort")
    if len(frame) < REQUIRED_HISTORY_ROWS:
        raise InsufficientHistoryError(
            f"requires {REQUIRED_HISTORY_ROWS} observations; found {len(frame)}"
        )
    window = frame.tail(REQUIRED_HISTORY_ROWS)
    latest_date = window.Date.iloc[-1]
    age = (cutoff.date() - latest_date.date()).days
    if age > MAX_MARKET_STALENESS_DAYS:
        raise StaleHistoryError(f"market data is stale by {age} days")
    if (window[["High", "Low", "Close"]] <= 0).any().any() or (window.Volume < 0).any():
        raise ValueError("market data contains invalid prices or volume")

    returns = window.Close.pct_change().dropna()
    volatility20 = returns.tail(20).std(ddof=1) * np.sqrt(252)
    volatility60 = returns.std(ddof=1) * np.sqrt(252)
    if not np.isfinite(volatility60) or volatility60 <= 0:
        raise ValueError("market data has zero or invalid volatility")
    sharpe = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
    max_drawdown = (window.Close / window.Close.cummax() - 1).min()
    previous_close = window.Close.shift(1)
    true_range = pd.concat([
        window.High - window.Low,
        (window.High - previous_close).abs(),
        (window.Low - previous_close).abs(),
    ], axis=1).max(axis=1)
    atr14 = true_range.tail(14).mean()
    liquidity = window.tail(20)
    latest_close = window.Close.iloc[-1]
    values = {
        "LatestClose": latest_close,
        "LatestCloseAsOf": latest_date.date().isoformat(),
        "MaxDrawdown": max_drawdown,
        "SharpeRatio": sharpe,
        "RiskObservationCount": len(window),
        "ObservationEndDate": latest_date.date().isoformat(),
        "Volatility20D": volatility20,
        "Volatility60D": volatility60,
        "ATR14": atr14,
        "ATRPercent": atr14 / latest_close,
        "AverageVolume20D": liquidity.Volume.mean(),
        "AverageDollarVolume20D": (liquidity.Close * liquidity.Volume).mean(),
        "LiquidityCoverage": liquidity[["Close", "Volume"]].notna().all(axis=1).mean(),
    }
    numeric_values = [value for key, value in values.items() if key not in {
        "LatestCloseAsOf", "ObservationEndDate",
    }]
    if not np.isfinite(numeric_values).all():
        raise ValueError("calculated risk inputs contain non-finite values")
    return values


def _risk_level(max_drawdown, sharpe):
    if max_drawdown >= -0.10 and sharpe >= 2:
        return "Low"
    if max_drawdown >= -0.25 and sharpe >= 1:
        return "Medium"
    return "High"


def _multiplier(level):
    return {
        "Low": LOW_RISK_WEIGHT_MULTIPLIER,
        "Medium": MEDIUM_RISK_WEIGHT_MULTIPLIER,
        "High": HIGH_RISK_WEIGHT_MULTIPLIER,
        "Unknown": UNKNOWN_RISK_WEIGHT_MULTIPLIER,
    }[level]


def calculate_portfolio_risk_inputs(candidates, *, market_data=None, calculation_timestamp=None, portfolio_snapshot=None):
    """Calculate eligible-candidate risk using no observations after AsOfDate."""
    del portfolio_snapshot  # P2.1 risk evidence does not depend on allocation state.
    source = _validate_candidates(candidates)
    eligible = source.loc[source.PortfolioEligible].copy()
    if eligible.empty:
        return empty_risk_inputs()
    timestamp = datetime.now(timezone.utc).isoformat() if calculation_timestamp is None else pd.Timestamp(calculation_timestamp).isoformat()
    rows = []
    for _, candidate in eligible.iterrows():
        base = candidate.to_dict()
        base.update({
            "RiskModelVersion": RISK_MODEL_VERSION,
            "CalculationTimestamp": timestamp,
            "BacktestScore": candidate.FinalScore,
            "BacktestScoreSemantic": "COMPATIBILITY_ALIAS_ONLY",
            "AverageReturn": np.nan,
            "WinRate": np.nan,
        })
        try:
            risk = _calculate_market_risk(candidate.Ticker, candidate.AsOfDate, market_data)
            level = _risk_level(risk["MaxDrawdown"], risk["SharpeRatio"])
            rows.append({**base, **risk, "RiskLevel": level,
                         "RiskWeightMultiplier": _multiplier(level),
                         "RiskStatus": "RISK_READY", "RiskReadyForPortfolio": True,
                         "RiskValidationReason": ""})
        except InsufficientHistoryError as error:
            rows.append({**base, "RiskLevel": "Unknown", "RiskWeightMultiplier": _multiplier("Unknown"),
                         "RiskStatus": "INSUFFICIENT_HISTORY", "RiskReadyForPortfolio": False,
                         "RiskValidationReason": str(error)})
        except StaleHistoryError as error:
            rows.append({**base, "RiskLevel": "Unknown", "RiskWeightMultiplier": _multiplier("Unknown"),
                         "RiskStatus": "STALE_HISTORY", "RiskReadyForPortfolio": False,
                         "RiskValidationReason": str(error)})
        except (KeyError, OSError, ValueError) as error:
            status = "INVALID_PRICE" if "price" in str(error).lower() else "INVALID_RISK_METRIC"
            rows.append({**base, "RiskLevel": "Unknown", "RiskWeightMultiplier": _multiplier("Unknown"),
                         "RiskStatus": status, "RiskReadyForPortfolio": False,
                         "RiskValidationReason": str(error)})
    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values(
        ["CandidateRank", "Ticker"], kind="mergesort"
    ).reset_index(drop=True)
    result.attrs["RiskBuildStatus"] = (
        RISK_INPUTS_READY if result.RiskReadyForPortfolio.any() else NO_RISK_READY_CANDIDATES
    )
    return result


def build_production_risk_inputs(*, input_path=DEFAULT_INPUT_PATH, output_path=DEFAULT_OUTPUT_PATH,
                                 market_data=None, calculation_timestamp=None):
    """Read the production authority, validate it, and write canonical risk inputs."""
    source = load_production_candidates(input_path)
    candidates = build_validated_portfolio_candidates(source)
    result = calculate_portfolio_risk_inputs(
        candidates, market_data=market_data, calculation_timestamp=calculation_timestamp
    )
    save_portfolio_risk_inputs(result, output_path)
    return result, Path(output_path)


def save_portfolio_risk_inputs(risk_inputs, output_path=DEFAULT_OUTPUT_PATH):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    risk_inputs.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_portfolio_risk_calculator(input_path=DEFAULT_INPUT_PATH, output_path=DEFAULT_OUTPUT_PATH, **kwargs):
    return build_production_risk_inputs(input_path=input_path, output_path=output_path, **kwargs)


if __name__ == "__main__":
    table, saved = build_production_risk_inputs()
    print(f"Production risk rows: {len(table)}")
    print(f"Risk ready: {int(table.RiskReadyForPortfolio.sum()) if not table.empty else 0}")
    print(f"Status: {table.attrs.get('RiskBuildStatus')}")
    print(f"Output: {saved}")
