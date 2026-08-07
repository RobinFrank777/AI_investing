"""Render the saved Universe150 research report as standalone Markdown."""

import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_report.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "universe150_research_report.md"
REPORT_COLUMNS = (
    "Rank",
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
    "LowVolScore",
    "CompositeScore",
)
NUMERIC_COLUMNS = tuple(column for column in REPORT_COLUMNS if column != "Ticker")
DATE_COLUMNS = ("ReportDate", "Report Date", "AsOfDate", "Date")


def load_research_report(input_path=None):
    """Load the Universe150 research-report CSV."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Universe150 research report file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Universe150 research report file is empty: {path}") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"Universe150 research report file is invalid: {path}") from error


def _validate_columns(report):
    missing = [column for column in REPORT_COLUMNS if column not in report]
    if missing:
        raise ValueError(
            "research report is missing required columns: " + ", ".join(missing)
        )


def _report_date(report):
    for column in DATE_COLUMNS:
        if column not in report:
            continue
        for value in report[column]:
            if pd.notna(value) and str(value).strip():
                return str(value).strip()
    return date.today().isoformat()


def _valid_records(report):
    _validate_columns(report)
    selected = report.loc[:, REPORT_COLUMNS].copy(deep=True)
    selected["Ticker"] = selected["Ticker"].fillna("").astype(str).str.strip()
    valid = selected["Ticker"].ne("")
    for column in NUMERIC_COLUMNS:
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
        valid &= selected[column].map(
            lambda value: pd.notna(value) and math.isfinite(value)
        )
    valid &= selected["Rank"].gt(0)
    return selected.loc[valid].reset_index(drop=True)


def _markdown_cell(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.10g}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report_markdown(report):
    """Render valid input records in their existing order without recalculation."""
    if not isinstance(report, pd.DataFrame):
        raise TypeError("report must be a pandas DataFrame")
    report_date = _report_date(report)
    valid = _valid_records(report)
    lines = [
        "# AI_investing Universe150 Research Report",
        "",
        f"- Report Date: {report_date}",
        "- Universe: Universe150",
        f"- Candidates Count: {len(valid)}",
        "",
    ]
    if valid.empty:
        lines.append("No valid research candidates.")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| " + " | ".join(REPORT_COLUMNS) + " |",
            "| " + " | ".join("---" for _ in REPORT_COLUMNS) + " |",
        ]
    )
    for row in valid.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(_markdown_cell(value) for value in row) + " |")
    lines.append("")
    return "\n".join(lines)


def generate_report(input_path=None, output_path=None):
    """Load the report CSV and write the Markdown report to the selected path."""
    report = load_research_report(input_path)
    markdown = render_report_markdown(report)
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def main():
    try:
        output = generate_report()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 report renderer error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 Research Report Renderer")
    print(f"Output: {output}")
    print("Research presentation only; no investment commentary was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
