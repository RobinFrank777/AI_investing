"""Build a validated, production-signal-based candidate artifact."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "stock_rank.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "production_candidates.csv"
MAX_STALENESS_DAYS = 5

SOURCE_COLUMNS = (
    "Ticker",
    "MarketDataDate",
    "FinalScore",
    "TradeSignal",
    "RS_Score",
    "NearHighScore",
    "Confidence",
    "ScoreModelVersion",
)
OUTPUT_COLUMNS = (
    "Ticker",
    "RunId",
    "AsOfDate",
    "CandidateRank",
    "Eligibility",
    "FinalScore",
    "TradeSignal",
    "RS_Score",
    "NearHighScore",
    "Confidence",
    "ScoreModelVersion",
)
NUMERIC_COLUMNS = (
    "FinalScore",
    "RS_Score",
    "NearHighScore",
    "Confidence",
)
ALLOWED_SIGNALS = frozenset({"BUY", "WATCH", "IGNORE"})


def empty_candidates() -> pd.DataFrame:
    """Return an empty candidate artifact with its stable schema."""
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def load_stock_rank(input_path=DEFAULT_INPUT_PATH) -> pd.DataFrame:
    """Load the production rank artifact without interpreting its values."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Production stock rank file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Production stock rank file is empty: {path}") from error
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Production stock rank file cannot be read: {path}") from error


def _normalize_reference_date(reference_date) -> date:
    if reference_date is None:
        return date.today()
    try:
        return pd.Timestamp(reference_date).date()
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("reference_date must be a valid date") from error


def _validate_and_normalize(source: pd.DataFrame, reference_date, max_staleness_days):
    if not isinstance(source, pd.DataFrame):
        raise TypeError("stock_rank must be a pandas DataFrame")
    if not isinstance(max_staleness_days, int) or max_staleness_days < 0:
        raise ValueError("max_staleness_days must be a non-negative integer")

    missing = [column for column in SOURCE_COLUMNS if column not in source]
    if missing:
        raise ValueError(
            "production stock rank missing required metadata: " + ", ".join(missing)
        )
    if source.empty:
        return source.loc[:, SOURCE_COLUMNS].copy(), None

    frame = source.loc[:, SOURCE_COLUMNS].copy()
    frame["Ticker"] = frame["Ticker"].fillna("").astype(str).str.strip().str.upper()
    if (frame["Ticker"] == "").any():
        raise ValueError("production stock rank contains missing Ticker metadata")
    duplicates = sorted(frame.loc[frame["Ticker"].duplicated(), "Ticker"].unique())
    if duplicates:
        raise ValueError("production stock rank contains duplicate ticker: " + ", ".join(duplicates))

    frame["ScoreModelVersion"] = (
        frame["ScoreModelVersion"].fillna("").astype(str).str.strip()
    )
    if (frame["ScoreModelVersion"] == "").any():
        raise ValueError("production stock rank contains missing ScoreModelVersion metadata")
    versions = frame["ScoreModelVersion"].unique().tolist()
    if len(versions) != 1:
        raise ValueError("production stock rank contains mixed ScoreModelVersion metadata")

    frame["TradeSignal"] = frame["TradeSignal"].fillna("").astype(str).str.strip().str.upper()
    invalid_signals = sorted(set(frame["TradeSignal"]) - ALLOWED_SIGNALS)
    if invalid_signals:
        raise ValueError("production stock rank contains invalid TradeSignal: " + ", ".join(invalid_signals))

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any() or not np.isfinite(frame[column]).all():
            raise ValueError(f"production stock rank contains non-finite {column}")

    try:
        parsed_dates = pd.to_datetime(frame["MarketDataDate"], errors="raise").dt.date
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("production stock rank contains invalid MarketDataDate metadata") from error
    if parsed_dates.isna().any():
        raise ValueError("production stock rank contains missing MarketDataDate metadata")
    as_of_dates = parsed_dates.unique().tolist()
    if len(as_of_dates) != 1:
        raise ValueError("production stock rank contains mixed MarketDataDate metadata")

    as_of_date = as_of_dates[0]
    age = (_normalize_reference_date(reference_date) - as_of_date).days
    if age < 0:
        raise ValueError("production stock rank AsOfDate is in the future")
    if age > max_staleness_days:
        raise ValueError(
            f"production stock rank is stale: AsOfDate {as_of_date.isoformat()} is {age} days old"
        )
    frame["MarketDataDate"] = as_of_date.isoformat()
    return frame, as_of_date


def _run_id(frame: pd.DataFrame, as_of_date: date) -> str:
    canonical = frame.sort_values("Ticker", kind="mergesort").to_csv(index=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"candidate-{as_of_date.strftime('%Y%m%d')}-{digest}"


def build_production_candidates(
    stock_rank: pd.DataFrame,
    *,
    reference_date=None,
    max_staleness_days=MAX_STALENESS_DAYS,
) -> pd.DataFrame:
    """Validate the current rank snapshot and build deterministic candidates."""
    frame, as_of_date = _validate_and_normalize(
        stock_rank, reference_date, max_staleness_days
    )
    if frame.empty:
        return empty_candidates()

    frame = frame.sort_values(
        ["FinalScore", "Ticker"],
        ascending=[False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    output = pd.DataFrame(
        {
            "Ticker": frame["Ticker"],
            "RunId": _run_id(frame, as_of_date),
            "AsOfDate": as_of_date.isoformat(),
            "CandidateRank": range(1, len(frame) + 1),
            "Eligibility": frame["TradeSignal"].map(
                lambda signal: "ELIGIBLE" if signal == "BUY" else "INELIGIBLE"
            ),
            "FinalScore": frame["FinalScore"],
            "TradeSignal": frame["TradeSignal"],
            "RS_Score": frame["RS_Score"],
            "NearHighScore": frame["NearHighScore"],
            "Confidence": frame["Confidence"],
            "ScoreModelVersion": frame["ScoreModelVersion"],
        }
    )
    return output.loc[:, OUTPUT_COLUMNS]


def save_production_candidates(candidates, output_path=DEFAULT_OUTPUT_PATH) -> Path:
    """Write candidates using the fixed output contract."""
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    missing = [column for column in OUTPUT_COLUMNS if column not in candidates]
    if missing:
        raise ValueError("production candidates missing columns: " + ", ".join(missing))
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_production_candidate_builder(
    input_path=DEFAULT_INPUT_PATH,
    output_path=DEFAULT_OUTPUT_PATH,
    *,
    reference_date=None,
    max_staleness_days=MAX_STALENESS_DAYS,
):
    """Load, validate, build, and save the production candidate artifact."""
    source = load_stock_rank(input_path)
    candidates = build_production_candidates(
        source,
        reference_date=reference_date,
        max_staleness_days=max_staleness_days,
    )
    path = save_production_candidates(candidates, output_path)
    return candidates, path


if __name__ == "__main__":
    candidate_table, saved_path = run_production_candidate_builder()
    print(f"Production candidates: {len(candidate_table)}")
    print(f"Eligible: {(candidate_table['Eligibility'] == 'ELIGIBLE').sum()}")
    print(f"Output: {saved_path}")
