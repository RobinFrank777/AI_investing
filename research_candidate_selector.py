"""Select research-only candidates from the saved Universe150 dataset."""

import math
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_raw.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_candidates.csv"
REQUIRED_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "CompositeSignal",
    "RiskStatus",
    "ResearchStatus",
)
OUTPUT_COLUMNS = REQUIRED_COLUMNS + ("CandidateStatus",)


def empty_candidates():
    """Return an empty candidate table with the stable output contract."""
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_research_data(input_path=None):
    """Load the research artifact, returning an empty contract if unavailable."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Universe150 research data cannot be read: {path}") from error


def candidate_status(research_status, risk_status):
    """Classify an existing research/risk state without deriving new metrics."""
    research = str(research_status).strip().upper()
    risk = str(risk_status).strip().upper()
    if research != "PASS":
        return "EXCLUDED"
    if risk == "PASS":
        return "READY"
    if risk == "PARTIAL":
        return "REVIEW"
    return "EXCLUDED"


def select_research_candidates(research):
    """Filter valid candidates and preserve their existing scores and ranks."""
    if not isinstance(research, pd.DataFrame):
        raise TypeError("research data must be a pandas DataFrame")
    missing = [column for column in REQUIRED_COLUMNS if column not in research]
    if missing:
        raise ValueError(
            "research data is missing required columns: " + ", ".join(missing)
        )
    if research.empty:
        return empty_candidates()

    rows = []
    for _, source in research.iterrows():
        ticker = "" if pd.isna(source["Ticker"]) else str(source["Ticker"]).strip()
        rank = _finite_number(source["Rank"])
        score = _finite_number(source["CompositeScore"])
        status = candidate_status(source["ResearchStatus"], source["RiskStatus"])
        if not ticker or rank is None or rank <= 0 or score is None:
            continue
        if status == "EXCLUDED":
            continue
        row = {column: source[column] for column in REQUIRED_COLUMNS}
        row["Ticker"] = ticker
        row["Rank"] = rank
        row["CompositeScore"] = score
        row["RiskStatus"] = str(source["RiskStatus"]).strip().upper()
        row["ResearchStatus"] = str(source["ResearchStatus"]).strip().upper()
        row["CandidateStatus"] = status
        rows.append(row)

    if not rows:
        return empty_candidates()
    candidates = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return candidates.sort_values("Rank", kind="stable").reset_index(drop=True)


def save_candidates(candidates, output_path=None):
    """Save selected candidates without modifying the source artifact."""
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_candidate_selector(input_path=None, output_path=None):
    """Load, select, and save Universe150 research candidates."""
    research = load_research_data(input_path)
    candidates = select_research_candidates(research)
    path = save_candidates(candidates, output_path)
    counts = candidates["CandidateStatus"].value_counts().to_dict()
    return {
        "candidates": candidates,
        "output_path": str(path),
        "summary": {
            "total": int(len(candidates)),
            "ready": int(counts.get("READY", 0)),
            "review": int(counts.get("REVIEW", 0)),
        },
    }


def main():
    try:
        result = run_candidate_selector()
    except (ValueError, TypeError, OSError) as error:
        print(f"Universe150 candidate selection error: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print("AI_investing Universe150 Research Candidates")
    print(f"Candidates: {summary['total']}")
    print(f"READY: {summary['ready']}")
    print(f"REVIEW: {summary['review']}")
    print(f"Output: {result['output_path']}")
    print("Research screening only; no recommendation or execution was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
