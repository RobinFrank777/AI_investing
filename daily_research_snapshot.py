"""Build a daily snapshot from the Universe150 candidate report."""

import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_candidate_report.csv"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "results" / "universe150_daily_research_snapshot.csv"
)
REQUIRED_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "CompositeSignal",
    "RiskStatus",
    "CandidateStatus",
    "ResearchPriority",
)
OUTPUT_COLUMNS = (
    "ReportDate",
    *REQUIRED_COLUMNS,
    "SnapshotStatus",
)


def empty_snapshot():
    """Return an empty snapshot with the stable output contract."""
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _formatted_date(value, fallback):
    if pd.isna(value) or str(value).strip() == "":
        return fallback
    try:
        parsed = pd.to_datetime(value, errors="raise")
    except (TypeError, ValueError, OverflowError):
        return fallback
    return parsed.date().isoformat()


def snapshot_status(candidate_status):
    """Map an existing candidate state to a snapshot state."""
    status = str(candidate_status).strip().upper()
    return "ACTIVE" if status in {"READY", "REVIEW"} else "INVALID"


def load_candidate_report(input_path=None):
    """Load the candidate report or return an empty input contract."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Universe150 candidate report cannot be read: {path}") from error


def build_daily_snapshot(candidate_report, generation_date=None):
    """Build snapshot rows while preserving saved values and row sequence."""
    if not isinstance(candidate_report, pd.DataFrame):
        raise TypeError("candidate report must be a pandas DataFrame")
    missing = [column for column in REQUIRED_COLUMNS if column not in candidate_report]
    if missing:
        raise ValueError(
            "candidate report is missing required columns: " + ", ".join(missing)
        )
    if candidate_report.empty:
        return empty_snapshot()

    fallback_date = (
        date.today().isoformat()
        if generation_date is None
        else _formatted_date(generation_date, date.today().isoformat())
    )
    has_report_date = "ReportDate" in candidate_report.columns
    text_columns = REQUIRED_COLUMNS[3:]
    rows = []
    for _, source in candidate_report.iterrows():
        ticker = "" if pd.isna(source["Ticker"]) else str(source["Ticker"]).strip()
        rank = _finite_number(source["Rank"])
        score = _finite_number(source["CompositeScore"])
        if (
            not ticker
            or rank is None
            or rank <= 0
            or score is None
            or any(pd.isna(source[column]) for column in text_columns)
        ):
            continue

        supplied_date = source["ReportDate"] if has_report_date else None
        row = {
            "ReportDate": _formatted_date(supplied_date, fallback_date),
            **{column: source[column] for column in REQUIRED_COLUMNS},
            "SnapshotStatus": snapshot_status(source["CandidateStatus"]),
        }
        row["Ticker"] = ticker
        row["Rank"] = rank
        row["CompositeScore"] = score
        rows.append(row)
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def save_daily_snapshot(snapshot, output_path=None):
    """Save the daily snapshot with its fixed field sequence."""
    if not isinstance(snapshot, pd.DataFrame):
        raise TypeError("snapshot must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_daily_snapshot(input_path=None, output_path=None, generation_date=None):
    """Load the report, build the snapshot, and save the artifact."""
    candidate_report = load_candidate_report(input_path)
    snapshot = build_daily_snapshot(candidate_report, generation_date=generation_date)
    path = save_daily_snapshot(snapshot, output_path)
    counts = snapshot["SnapshotStatus"].value_counts().to_dict()
    return {
        "snapshot": snapshot,
        "output_path": str(path),
        "summary": {
            "rows": int(len(snapshot)),
            "active": int(counts.get("ACTIVE", 0)),
            "invalid": int(counts.get("INVALID", 0)),
        },
    }


def main():
    try:
        result = run_daily_snapshot()
    except (ValueError, TypeError, OSError) as error:
        print(f"Universe150 daily snapshot error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 Daily Research Snapshot")
    print(f"Rows: {result['summary']['rows']}")
    print(f"ACTIVE: {result['summary']['active']}")
    print(f"INVALID: {result['summary']['invalid']}")
    print(f"Output: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
