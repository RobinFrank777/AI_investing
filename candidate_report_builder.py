"""Build the Universe150 candidate research presentation artifact."""

import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from research_schema import normalize_research_schema


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_candidates.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_candidate_report.csv"
SOURCE_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "CompositeSignal",
    "Signal",
    "RiskStatus",
    "CandidateStatus",
)
OUTPUT_COLUMNS = SOURCE_COLUMNS + ("ResearchPriority", "ReportDate")


def empty_candidate_report():
    """Return an empty report with the fixed column contract."""
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


def research_priority(candidate_status):
    """Map an existing candidate state to its display priority."""
    status = str(candidate_status).strip().upper()
    if status == "READY":
        return "HIGH"
    if status == "REVIEW":
        return "MEDIUM"
    return "LOW"


def load_candidates(input_path=None):
    """Load candidates, returning an empty contract when the file is absent."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Universe150 candidate data cannot be read: {path}") from error


def build_candidate_report(candidates, generation_date=None):
    """Build display rows without changing saved ranks, scores, or signals."""
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    candidate_source = normalize_research_schema(candidates)
    missing = [column for column in SOURCE_COLUMNS if column not in candidate_source]
    if missing:
        raise ValueError(
            "candidate data is missing required columns: " + ", ".join(missing)
        )
    if candidate_source.empty:
        return empty_candidate_report()

    fallback_date = (
        date.today().isoformat()
        if generation_date is None
        else _formatted_date(generation_date, date.today().isoformat())
    )
    has_report_date = "ReportDate" in candidate_source.columns
    rows = []
    for _, source in candidate_source.iterrows():
        ticker = "" if pd.isna(source["Ticker"]) else str(source["Ticker"]).strip()
        rank = _finite_number(source["Rank"])
        score = _finite_number(source["CompositeScore"])
        required_text = SOURCE_COLUMNS[3:]
        if (
            not ticker
            or rank is None
            or rank <= 0
            or score is None
            or any(pd.isna(source[column]) for column in required_text)
        ):
            continue

        row = {column: source[column] for column in SOURCE_COLUMNS}
        row["Ticker"] = ticker
        row["Rank"] = rank
        row["CompositeScore"] = score
        row["ResearchPriority"] = research_priority(source["CandidateStatus"])
        supplied_date = source["ReportDate"] if has_report_date else None
        row["ReportDate"] = _formatted_date(supplied_date, fallback_date)
        rows.append(row)
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def save_candidate_report(report, output_path=None):
    """Save a candidate report with its fixed field sequence."""
    if not isinstance(report, pd.DataFrame):
        raise TypeError("report must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_candidate_report(input_path=None, output_path=None, generation_date=None):
    """Load candidate rows, build their presentation, and save the result."""
    candidates = load_candidates(input_path)
    report = build_candidate_report(candidates, generation_date=generation_date)
    path = save_candidate_report(report, output_path)
    return {
        "report": report,
        "output_path": str(path),
        "summary": {"rows": int(len(report))},
    }


def main():
    try:
        result = run_candidate_report()
    except (ValueError, TypeError, OSError) as error:
        print(f"Universe150 candidate report error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 Candidate Report")
    print(f"Rows: {result['summary']['rows']}")
    print(f"Output: {result['output_path']}")
    print("Research presentation only; no action was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
