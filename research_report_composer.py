"""Compose a Markdown report from Universe150 AI research summaries."""

import math
import sys
from pathlib import Path

import pandas as pd

from research_schema import normalize_research_schema


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = (
    PROJECT_ROOT / "results" / "universe150_ai_research_summary.csv"
)
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_report.md"
REQUIRED_COLUMNS = (
    "Rank",
    "Ticker",
    "CompositeScore",
    "Signal",
    "ResearchTone",
    "ResearchSummary",
    "AIResearchSummary",
    "ReportDate",
)
EMPTY_REPORT = "# AI_investing Research Report\n\nNo research candidates available.\n"


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _display_number(value):
    number = _finite_number(value)
    if number is None:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def _text(value):
    return "" if pd.isna(value) else str(value).strip()


def load_ai_research_summary(input_path=None):
    """Load the summary artifact or return an empty valid input contract."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Universe150 AI research summary cannot be read: {path}") from error


def compose_research_report(summaries):
    """Render valid summary rows in their supplied sequence."""
    if not isinstance(summaries, pd.DataFrame):
        raise TypeError("summaries must be a pandas DataFrame")
    summary_source = normalize_research_schema(summaries)
    missing = [column for column in REQUIRED_COLUMNS if column not in summary_source]
    if missing:
        raise ValueError(
            "AI research summary is missing required columns: " + ", ".join(missing)
        )
    if summary_source.empty:
        return EMPTY_REPORT

    candidates = []
    for _, source in summary_source.iterrows():
        rank = _finite_number(source["Rank"])
        score = _finite_number(source["CompositeScore"])
        fields = {
            column: _text(source[column])
            for column in (
                "Ticker",
                "Signal",
                "ResearchTone",
                "ResearchSummary",
                "AIResearchSummary",
                "ReportDate",
            )
        }
        if rank is None or rank <= 0 or score is None or not all(fields.values()):
            continue
        candidates.append((rank, score, fields))

    if not candidates:
        return EMPTY_REPORT

    lines = [
        "# AI_investing Research Report",
        "",
        "Report Date:",
        candidates[0][2]["ReportDate"],
        "",
        "## Research Candidates",
        "",
    ]
    for index, (rank, score, fields) in enumerate(candidates):
        lines.extend(
            (
                f"### Rank {_display_number(rank)} - {fields['Ticker']}",
                "",
                "Composite Score:",
                _display_number(score),
                "",
                "Signal:",
                fields["Signal"],
                "",
                "Research Tone:",
                fields["ResearchTone"],
                "",
                "Research Summary:",
                "",
                fields["ResearchSummary"],
                "",
                "AI Research Summary:",
                "",
                fields["AIResearchSummary"],
                "",
            )
        )
        if index < len(candidates) - 1:
            lines.extend(("---", ""))
    return "\n".join(lines).rstrip() + "\n"


def save_research_report(markdown, output_path=None):
    """Save a composed Markdown report."""
    if not isinstance(markdown, str):
        raise TypeError("markdown must be a string")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def generate_research_report(input_path=None, output_path=None):
    """Load summaries, compose Markdown, and save the report."""
    summaries = load_ai_research_summary(input_path)
    markdown = compose_research_report(summaries)
    path = save_research_report(markdown, output_path)
    return {"markdown": markdown, "report_path": str(path)}


def main():
    try:
        result = generate_research_report()
    except (ValueError, TypeError, OSError) as error:
        print(f"Universe150 research report error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 Research Report")
    print(f"Output: {result['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
