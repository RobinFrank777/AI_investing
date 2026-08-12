"""Validate production candidates for the portfolio-consumer boundary."""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "production_candidates.csv"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "results" / "validated_portfolio_candidates.csv"
)

SOURCE_COLUMNS = (
    "Ticker",
    "AsOfDate",
    "RunId",
    "ScoreModelVersion",
    "CandidateRank",
    "FinalScore",
    "TradeSignal",
    "Eligibility",
)
OUTPUT_COLUMNS = SOURCE_COLUMNS + (
    "PortfolioEligible",
    "ValidationStatus",
    "ValidationReason",
)
ALLOWED_SIGNALS = frozenset({"BUY", "WATCH", "IGNORE"})
ALLOWED_ELIGIBILITY = frozenset({"ELIGIBLE", "INELIGIBLE"})


def empty_portfolio_candidates():
    """Return a stable header-only portfolio candidate contract."""
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def load_production_candidates(input_path=DEFAULT_INPUT_PATH):
    """Load the production candidate artifact without modifying it."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Production candidate file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Production candidate file is empty: {path}") from error
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Production candidate file cannot be read: {path}") from error


def _required_columns(source):
    missing = [column for column in SOURCE_COLUMNS if column not in source]
    if missing:
        raise ValueError(
            "production candidates missing required columns: " + ", ".join(missing)
        )


def _normalize_text(frame, column):
    frame[column] = frame[column].fillna("").astype(str).str.strip()
    if (frame[column] == "").any():
        raise ValueError(f"production candidates contain missing {column}")


def _require_single_value(frame, column):
    values = frame[column].unique().tolist()
    if len(values) != 1:
        raise ValueError(f"production candidates contain mixed {column}")


def _validate_and_normalize(candidates):
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    _required_columns(candidates)
    if candidates.empty:
        return candidates.loc[:, SOURCE_COLUMNS].copy()

    frame = candidates.loc[:, SOURCE_COLUMNS].copy()
    for column in ("Ticker", "AsOfDate", "RunId", "ScoreModelVersion"):
        _normalize_text(frame, column)

    frame["Ticker"] = frame["Ticker"].str.upper()
    duplicates = sorted(frame.loc[frame["Ticker"].duplicated(), "Ticker"].unique())
    if duplicates:
        raise ValueError(
            "production candidates contain duplicate ticker: "
            + ", ".join(duplicates)
        )

    for column in ("RunId", "AsOfDate", "ScoreModelVersion"):
        _require_single_value(frame, column)

    try:
        parsed_dates = pd.to_datetime(frame["AsOfDate"], errors="raise")
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("production candidates contain invalid AsOfDate") from error
    if parsed_dates.isna().any():
        raise ValueError("production candidates contain missing AsOfDate")
    frame["AsOfDate"] = parsed_dates.dt.date.astype(str)

    frame["FinalScore"] = pd.to_numeric(frame["FinalScore"], errors="coerce")
    if frame["FinalScore"].isna().any() or not np.isfinite(frame["FinalScore"]).all():
        raise ValueError("production candidates contain non-finite FinalScore")

    frame["CandidateRank"] = pd.to_numeric(frame["CandidateRank"], errors="coerce")
    if (
        frame["CandidateRank"].isna().any()
        or not np.isfinite(frame["CandidateRank"]).all()
        or (frame["CandidateRank"] <= 0).any()
        or (frame["CandidateRank"] % 1 != 0).any()
        or frame["CandidateRank"].duplicated().any()
    ):
        raise ValueError("production candidates contain invalid CandidateRank")
    frame["CandidateRank"] = frame["CandidateRank"].astype(int)

    frame["TradeSignal"] = (
        frame["TradeSignal"].fillna("").astype(str).str.strip().str.upper()
    )
    invalid_signals = sorted(set(frame["TradeSignal"]) - ALLOWED_SIGNALS)
    if invalid_signals:
        raise ValueError(
            "production candidates contain invalid TradeSignal: "
            + ", ".join(invalid_signals)
        )

    frame["Eligibility"] = (
        frame["Eligibility"].fillna("").astype(str).str.strip().str.upper()
    )
    invalid_eligibility = sorted(
        set(frame["Eligibility"]) - ALLOWED_ELIGIBILITY
    )
    if invalid_eligibility:
        raise ValueError(
            "production candidates contain invalid Eligibility: "
            + ", ".join(invalid_eligibility)
        )
    return frame


def build_validated_portfolio_candidates(candidates):
    """Apply the production-signal safety boundary without inventing risk data."""
    frame = _validate_and_normalize(candidates)
    if frame.empty:
        return empty_portfolio_candidates()

    accepted = (frame["TradeSignal"] == "BUY") & (
        frame["Eligibility"] == "ELIGIBLE"
    )
    output = frame.copy()
    output["PortfolioEligible"] = accepted
    output["ValidationStatus"] = np.where(
        accepted,
        "RISK_INPUT_PENDING",
        "NOT_PORTFOLIO_ELIGIBLE",
    )
    output["ValidationReason"] = np.select(
        [
            accepted,
            frame["TradeSignal"] == "WATCH",
            frame["TradeSignal"] == "IGNORE",
            frame["Eligibility"] != "ELIGIBLE",
        ],
        [
            "BUY signal accepted; portfolio risk inputs are pending",
            "WATCH signal is not portfolio eligible",
            "IGNORE signal is not portfolio eligible",
            "candidate Eligibility is not ELIGIBLE",
        ],
        default="candidate is not portfolio eligible",
    )
    return output.loc[:, OUTPUT_COLUMNS].sort_values(
        ["CandidateRank", "Ticker"], kind="mergesort"
    ).reset_index(drop=True)


def save_validated_portfolio_candidates(
    candidates, output_path=DEFAULT_OUTPUT_PATH
):
    """Save a validated portfolio candidate artifact with a fixed schema."""
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    missing = [column for column in OUTPUT_COLUMNS if column not in candidates]
    if missing:
        raise ValueError(
            "validated portfolio candidates missing columns: " + ", ".join(missing)
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_portfolio_candidate_adapter(
    input_path=DEFAULT_INPUT_PATH,
    output_path=DEFAULT_OUTPUT_PATH,
):
    """Load, validate, and save the portfolio candidate boundary artifact."""
    source = load_production_candidates(input_path)
    validated = build_validated_portfolio_candidates(source)
    path = save_validated_portfolio_candidates(validated, output_path)
    return validated, path


if __name__ == "__main__":
    table, saved_path = run_portfolio_candidate_adapter()
    print(f"Validated portfolio candidates: {len(table)}")
    print(f"Portfolio eligible: {int(table['PortfolioEligible'].sum())}")
    print(f"Output: {saved_path}")
