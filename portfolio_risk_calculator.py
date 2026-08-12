"""Calculate point-in-time portfolio risk inputs for validated candidates."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from stock_loader import load_stock


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "validated_portfolio_candidates.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "portfolio_risk_inputs.csv"
RISK_MODEL_VERSION = "portfolio-risk-v3.8.1-r1"
REQUIRED_HISTORY_ROWS = 60
MAX_MARKET_STALENESS_DAYS = 5

CANDIDATE_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "ScoreModelVersion", "FinalScore",
    "TradeSignal", "PortfolioEligible",
)
OUTPUT_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "ScoreModelVersion", "RiskModelVersion",
    "PortfolioSnapshotId", "PortfolioAsOfDate", "ObservationEndDate",
    "CalculationTimestamp",
    "RiskObservationCount", "Volatility20D", "Volatility60D",
    "TrailingDrawdown", "ATR14", "AverageVolume20D",
    "AverageDollarVolume20D", "LiquidityCoverage",
    "CurrentPortfolioWeight", "RiskStatus", "RiskValidationStatus",
    "RiskValidationReason",
)
SNAPSHOT_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "PortfolioSnapshotId",
    "PortfolioAsOfDate", "CurrentPortfolioWeight",
)


def empty_risk_inputs():
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def load_validated_candidates(path=DEFAULT_INPUT_PATH):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Validated candidate file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Validated candidate file is empty: {path}") from error


def _single(frame, column):
    values = frame[column].unique().tolist()
    if len(values) != 1:
        raise ValueError(f"validated candidates contain mixed {column}")


def _validate_candidates(candidates):
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    missing = [column for column in CANDIDATE_COLUMNS if column not in candidates]
    if missing:
        raise ValueError("validated candidates missing columns: " + ", ".join(missing))
    if candidates.empty:
        return candidates.copy()
    frame = candidates.copy(deep=True)
    for column in ("Ticker", "RunId", "AsOfDate", "ScoreModelVersion"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise ValueError(f"validated candidates contain missing {column}")
    frame["Ticker"] = frame["Ticker"].str.upper()
    duplicates = sorted(frame.loc[frame.Ticker.duplicated(), "Ticker"].unique())
    if duplicates:
        raise ValueError("validated candidates contain duplicate ticker: " + ", ".join(duplicates))
    for column in ("RunId", "AsOfDate", "ScoreModelVersion"):
        _single(frame, column)
    try:
        frame["AsOfDate"] = pd.to_datetime(frame["AsOfDate"], errors="raise").dt.date.astype(str)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("validated candidates contain invalid AsOfDate") from error
    frame["FinalScore"] = pd.to_numeric(frame["FinalScore"], errors="coerce")
    if frame.FinalScore.isna().any() or not np.isfinite(frame.FinalScore).all():
        raise ValueError("validated candidates contain non-finite FinalScore")
    eligible = frame["PortfolioEligible"]
    if eligible.dtype != bool:
        mapping = {"TRUE": True, "FALSE": False}
        eligible = eligible.astype(str).str.strip().str.upper().map(mapping)
    if eligible.isna().any():
        raise ValueError("validated candidates contain invalid PortfolioEligible")
    frame["PortfolioEligible"] = eligible.astype(bool)
    invalid_promotion = frame.PortfolioEligible & (frame.TradeSignal.astype(str).str.upper() != "BUY")
    if invalid_promotion.any():
        raise ValueError("PortfolioEligible candidate must preserve BUY TradeSignal")
    return frame


def _validate_snapshot(snapshot, candidates):
    if snapshot is None:
        return None
    if not isinstance(snapshot, pd.DataFrame):
        raise TypeError("portfolio_snapshot must be a pandas DataFrame")
    missing = [column for column in SNAPSHOT_COLUMNS if column not in snapshot]
    if missing:
        raise ValueError("portfolio snapshot missing columns: " + ", ".join(missing))
    frame = snapshot.loc[:, SNAPSHOT_COLUMNS].copy()
    if frame.empty:
        return frame
    for column in ("Ticker", "RunId", "AsOfDate", "PortfolioSnapshotId", "PortfolioAsOfDate"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise ValueError(f"portfolio snapshot contains missing {column}")
    frame["Ticker"] = frame.Ticker.str.upper()
    if frame.Ticker.duplicated().any():
        raise ValueError("portfolio snapshot contains duplicate ticker")
    for column in ("RunId", "AsOfDate", "PortfolioSnapshotId", "PortfolioAsOfDate"):
        _single(frame, column)
    try:
        frame["AsOfDate"] = pd.to_datetime(frame.AsOfDate, errors="raise").dt.date.astype(str)
        frame["PortfolioAsOfDate"] = pd.to_datetime(
            frame.PortfolioAsOfDate, errors="raise"
        ).dt.date.astype(str)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("portfolio snapshot contains invalid date metadata") from error
    if not candidates.empty:
        if frame.RunId.iloc[0] != candidates.RunId.iloc[0] or frame.AsOfDate.iloc[0] != candidates.AsOfDate.iloc[0]:
            raise ValueError("portfolio snapshot provenance conflicts with candidates")
        if frame.PortfolioAsOfDate.iloc[0] > candidates.AsOfDate.iloc[0]:
            raise ValueError("portfolio snapshot uses future portfolio state")
    frame["CurrentPortfolioWeight"] = pd.to_numeric(frame.CurrentPortfolioWeight, errors="coerce")
    if frame.CurrentPortfolioWeight.isna().any() or not np.isfinite(frame.CurrentPortfolioWeight).all():
        raise ValueError("portfolio snapshot contains non-finite CurrentPortfolioWeight")
    if ((frame.CurrentPortfolioWeight < 0) | (frame.CurrentPortfolioWeight > 1)).any():
        raise ValueError("portfolio snapshot contains invalid CurrentPortfolioWeight")
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
    if frame.Date.isna().any():
        raise ValueError("market data contains invalid dates")
    cutoff = pd.Timestamp(as_of_date)
    frame = frame.loc[frame.Date <= cutoff].copy()
    for column in ("High", "Low", "Close", "Volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.Date.duplicated().any():
        raise ValueError("market data contains duplicate dates")
    if not np.isfinite(frame[["High", "Low", "Close", "Volume"]]).all().all():
        raise ValueError("market data contains non-finite values")
    frame = frame.sort_values("Date", kind="mergesort")
    if len(frame) < REQUIRED_HISTORY_ROWS:
        raise LookupError(f"requires {REQUIRED_HISTORY_ROWS} observations; found {len(frame)}")
    window = frame.tail(REQUIRED_HISTORY_ROWS)
    observation_end = window.Date.iloc[-1]
    age = (cutoff.date() - observation_end.date()).days
    if age > MAX_MARKET_STALENESS_DAYS:
        raise LookupError(f"market data is stale by {age} days")
    if (window[["High", "Low", "Close"]] <= 0).any().any() or (window.Volume < 0).any():
        raise ValueError("market data contains invalid prices or volume")

    returns = window.Close.pct_change().dropna()
    vol20 = returns.tail(20).std(ddof=1) * np.sqrt(252)
    vol60 = returns.std(ddof=1) * np.sqrt(252)
    trailing_drawdown = window.Close.iloc[-1] / window.Close.cummax().iloc[-1] - 1
    previous_close = window.Close.shift(1)
    true_range = pd.concat(
        [window.High - window.Low, (window.High - previous_close).abs(), (window.Low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr14 = true_range.tail(14).mean()
    liquidity = window.tail(20)
    values = {
        "ObservationEndDate": observation_end.date().isoformat(),
        "RiskObservationCount": len(window),
        "Volatility20D": vol20,
        "Volatility60D": vol60,
        "TrailingDrawdown": trailing_drawdown,
        "ATR14": atr14,
        "AverageVolume20D": liquidity.Volume.mean(),
        "AverageDollarVolume20D": (liquidity.Close * liquidity.Volume).mean(),
        "LiquidityCoverage": liquidity[["Close", "Volume"]].notna().all(axis=1).mean(),
    }
    if not np.isfinite(list(values.values())[1:]).all():
        raise ValueError("calculated risk inputs contain non-finite values")
    return values


def calculate_portfolio_risk_inputs(
    candidates, *, market_data=None, portfolio_snapshot=None,
    calculation_timestamp=None,
):
    """Calculate risk using only observations at or before candidate AsOfDate."""
    source = _validate_candidates(candidates)
    eligible = source.loc[source.PortfolioEligible].copy()
    if eligible.empty:
        return empty_risk_inputs()
    if calculation_timestamp is None:
        calculation_timestamp = datetime.now(timezone.utc).isoformat()
    else:
        calculation_timestamp = pd.Timestamp(calculation_timestamp).isoformat()
    snapshot = _validate_snapshot(portfolio_snapshot, source)
    snapshot_lookup = {} if snapshot is None else snapshot.set_index("Ticker").to_dict("index")
    rows = []
    for _, candidate in eligible.iterrows():
        base = {
            "Ticker": candidate.Ticker, "RunId": candidate.RunId,
            "AsOfDate": candidate.AsOfDate,
            "ScoreModelVersion": candidate.ScoreModelVersion,
            "RiskModelVersion": RISK_MODEL_VERSION,
            "CalculationTimestamp": calculation_timestamp,
        }
        snap = snapshot_lookup.get(candidate.Ticker)
        if snap is None:
            rows.append({
                **base, "RiskStatus": "PENDING", "RiskValidationStatus": "FAILED",
                "RiskValidationReason": "PORTFOLIO_SNAPSHOT_MISSING",
            })
            continue
        base.update({
            "PortfolioSnapshotId": snap["PortfolioSnapshotId"],
            "PortfolioAsOfDate": snap["PortfolioAsOfDate"],
            "CurrentPortfolioWeight": snap["CurrentPortfolioWeight"],
        })
        try:
            risk = _calculate_market_risk(candidate.Ticker, candidate.AsOfDate, market_data)
            rows.append({
                **base, **risk, "RiskStatus": "READY",
                "RiskValidationStatus": "PASS", "RiskValidationReason": "",
            })
        except LookupError as error:
            rows.append({
                **base, "RiskStatus": "PENDING", "RiskValidationStatus": "FAILED",
                "RiskValidationReason": str(error),
            })
        except (KeyError, OSError, ValueError) as error:
            rows.append({
                **base, "RiskStatus": "BLOCKED", "RiskValidationStatus": "FAILED",
                "RiskValidationReason": str(error),
            })
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values("Ticker", kind="mergesort").reset_index(drop=True)


def save_portfolio_risk_inputs(risk_inputs, output_path=DEFAULT_OUTPUT_PATH):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    risk_inputs.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_portfolio_risk_calculator(input_path=DEFAULT_INPUT_PATH, output_path=DEFAULT_OUTPUT_PATH, *, portfolio_snapshot=None):
    candidates = load_validated_candidates(input_path)
    result = calculate_portfolio_risk_inputs(candidates, portfolio_snapshot=portfolio_snapshot)
    path = save_portfolio_risk_inputs(result, output_path)
    return result, path


if __name__ == "__main__":
    table, saved = run_portfolio_risk_calculator()
    print(f"Portfolio risk rows: {len(table)}")
    print(f"PASS: {(table.RiskValidationStatus == 'PASS').sum() if not table.empty else 0}")
    print(f"Output: {saved}")
