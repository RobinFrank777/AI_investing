"""Build local template summaries from Universe150 research explanations."""

import math
import sys
from pathlib import Path

import pandas as pd

from research_schema import normalize_research_schema


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = (
    PROJECT_ROOT / "results" / "universe150_research_explanation.csv"
)
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "results" / "universe150_ai_research_summary.csv"
)
REQUIRED_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "Signal",
    "ResearchTone",
    "ResearchSummary",
    "ReportDate",
)
OUTPUT_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "Signal",
    "ResearchTone",
    "ResearchSummary",
    "AIResearchSummary",
    "ReportDate",
)
POSITIVE_SUMMARY = (
    "Positive technical profile with favorable trend, momentum and volatility "
    "characteristics. Candidate deserves further fundamental review."
)
CAUTION_SUMMARY = (
    "Risk signals require additional investigation before considering this candidate."
)
NEUTRAL_SUMMARY = "Mixed quantitative signals suggest neutral research priority."


def empty_ai_summaries():
    """Return an empty table with the fixed output contract."""
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_template_summary(research_tone):
    """Return the fixed local template for an existing research tone."""
    tone = str(research_tone).strip().upper()
    if tone == "POSITIVE":
        return POSITIVE_SUMMARY
    if tone == "CAUTION":
        return CAUTION_SUMMARY
    return NEUTRAL_SUMMARY


def load_research_explanations(input_path=None):
    """Load explanations or return an empty input contract when absent."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Universe150 research explanations cannot be read: {path}") from error


def build_ai_research_summaries(explanations):
    """Build local summaries while preserving supplied values and row sequence."""
    if not isinstance(explanations, pd.DataFrame):
        raise TypeError("explanations must be a pandas DataFrame")
    explanation_source = normalize_research_schema(explanations)
    missing = [column for column in REQUIRED_COLUMNS if column not in explanation_source]
    if missing:
        raise ValueError(
            "research explanations are missing required columns: "
            + ", ".join(missing)
        )
    if explanation_source.empty:
        return empty_ai_summaries()

    rows = []
    text_columns = REQUIRED_COLUMNS[3:]
    for _, source in explanation_source.iterrows():
        ticker = "" if pd.isna(source["Ticker"]) else str(source["Ticker"]).strip()
        rank = _finite_number(source["Rank"])
        score = _finite_number(source["CompositeScore"])
        if (
            not ticker
            or rank is None
            or rank <= 0
            or score is None
            or any(
                pd.isna(source[column]) or not str(source[column]).strip()
                for column in text_columns
            )
        ):
            continue

        tone = str(source["ResearchTone"]).strip().upper()
        rows.append(
            {
                "Ticker": ticker,
                "Rank": rank,
                "CompositeScore": score,
                "Signal": source["Signal"],
                "ResearchTone": tone,
                "ResearchSummary": source["ResearchSummary"],
                "AIResearchSummary": build_template_summary(tone),
                "ReportDate": source["ReportDate"],
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def save_ai_research_summaries(summaries, output_path=None):
    """Save local summaries with their fixed field sequence."""
    if not isinstance(summaries, pd.DataFrame):
        raise TypeError("summaries must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summaries.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_ai_research_summary_builder(input_path=None, output_path=None):
    """Load explanations, apply templates, and save the artifact."""
    explanations = load_research_explanations(input_path)
    summaries = build_ai_research_summaries(explanations)
    path = save_ai_research_summaries(summaries, output_path)
    return {
        "summaries": summaries,
        "output_path": str(path),
        "summary": {"rows": int(len(summaries))},
    }


def main():
    try:
        result = run_ai_research_summary_builder()
    except (ValueError, TypeError, OSError) as error:
        print(f"Universe150 AI research summary error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 AI Research Summary")
    print(f"Rows: {result['summary']['rows']}")
    print(f"Output: {result['output_path']}")
    print("Local templates only; no external AI service was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
