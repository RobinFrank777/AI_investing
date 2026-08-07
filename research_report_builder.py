"""Build the Universe150 Top-N research report from saved factor rankings."""

import math
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_factor_ranking.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_report.csv"
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


def _validate_top_n(top_n):
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0:
        raise ValueError("top_n must be a positive integer")
    return top_n


def load_factor_ranking(input_path=None):
    """Load the saved Universe150 factor-ranking artifact."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Universe150 factor ranking file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Universe150 factor ranking file is empty: {path}") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"Universe150 factor ranking file is invalid: {path}") from error


def build_research_report(ranking, top_n=10):
    """Return valid ranked records sorted by ascending Rank and limited to Top N."""
    selected_top_n = _validate_top_n(top_n)
    if not isinstance(ranking, pd.DataFrame):
        raise TypeError("ranking must be a pandas DataFrame")
    missing = [column for column in REPORT_COLUMNS if column not in ranking]
    if missing:
        raise ValueError(
            "factor ranking is missing required columns: " + ", ".join(missing)
        )

    report = ranking.loc[:, REPORT_COLUMNS].copy(deep=True)
    report["Ticker"] = report["Ticker"].fillna("").astype(str).str.strip()
    for column in NUMERIC_COLUMNS:
        report[column] = pd.to_numeric(report[column], errors="coerce")

    valid_rank = report["Rank"].map(
        lambda value: pd.notna(value) and math.isfinite(value) and value > 0
    )
    valid_score = report["CompositeScore"].map(
        lambda value: pd.notna(value) and math.isfinite(value)
    )
    valid_ticker = report["Ticker"].ne("")
    report = report.loc[valid_rank & valid_score & valid_ticker]
    report = report.sort_values("Rank", kind="mergesort").head(selected_top_n)
    return report.reset_index(drop=True).loc[:, REPORT_COLUMNS]


def save_research_report(report, output_path=None):
    """Save an already-built Universe150 research report without an index."""
    if not isinstance(report, pd.DataFrame):
        raise TypeError("report must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(path, index=False)
    return path


def run_research_report(input_path=None, output_path=None, *, top_n=10):
    """Load ranking data, build the Top-N report, and save the CSV artifact."""
    ranking = load_factor_ranking(input_path)
    report = build_research_report(ranking, top_n=top_n)
    path = save_research_report(report, output_path)
    return {
        "report": report,
        "output_path": str(path),
        "summary": {"rows": int(len(report)), "top_n": int(top_n)},
    }


def main():
    try:
        result = run_research_report()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 research report error: {error}", file=sys.stderr)
        return 1

    print("AI_investing Universe150 Research Report")
    print(f"Rows: {result['summary']['rows']}")
    print(f"Top N: {result['summary']['top_n']}")
    print(f"Output: {result['output_path']}")
    print("Research presentation only; no trading recommendation was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
