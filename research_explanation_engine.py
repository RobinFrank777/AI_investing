"""Generate rule-based explanations for Universe150 research snapshots."""

import math
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = (
    PROJECT_ROOT / "results" / "universe150_daily_research_snapshot.csv"
)
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "results" / "universe150_research_explanation.csv"
)
REQUIRED_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "SnapshotStatus",
    "ReportDate",
)
OUTPUT_COLUMNS = (
    "Ticker",
    "Rank",
    "CompositeScore",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "ResearchTone",
    "ResearchSummary",
    "ReportDate",
)


def empty_explanations():
    """Return an empty explanation table with the fixed output contract."""
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def research_tone(trend_signal, momentum_signal, volatility_signal):
    """Classify the supplied signal combination with fixed research rules."""
    trend = str(trend_signal).strip().upper()
    momentum = str(momentum_signal).strip().upper()
    volatility = str(volatility_signal).strip().upper()
    if trend == "BULLISH" and momentum == "STRONG" and volatility == "LOW":
        return "POSITIVE"
    if trend == "BEARISH" or momentum == "WEAK":
        return "CAUTION"
    return "NEUTRAL"


def research_summary(tone):
    """Return stable explanatory text for a research tone."""
    if tone == "POSITIVE":
        return "Strong trend and momentum with controlled volatility."
    if tone == "CAUTION":
        return "Weak trend or momentum signals require caution."
    return "Mixed signals require further review."


def load_daily_snapshot(input_path=None):
    """Load the daily snapshot or return an empty input contract."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        raise ValueError(f"Universe150 daily snapshot cannot be read: {path}") from error


def build_research_explanations(snapshot):
    """Build explanations while preserving the supplied row sequence and values."""
    if not isinstance(snapshot, pd.DataFrame):
        raise TypeError("snapshot must be a pandas DataFrame")
    missing = [column for column in REQUIRED_COLUMNS if column not in snapshot]
    if missing:
        raise ValueError(
            "daily snapshot is missing required columns: " + ", ".join(missing)
        )
    if snapshot.empty:
        return empty_explanations()

    rows = []
    for _, source in snapshot.iterrows():
        ticker = "" if pd.isna(source["Ticker"]) else str(source["Ticker"]).strip()
        rank = _finite_number(source["Rank"])
        score = _finite_number(source["CompositeScore"])
        signals = [
            "" if pd.isna(source[column]) else str(source[column]).strip().upper()
            for column in ("TrendSignal", "MomentumSignal", "VolatilitySignal")
        ]
        snapshot_status = (
            ""
            if pd.isna(source["SnapshotStatus"])
            else str(source["SnapshotStatus"]).strip().upper()
        )
        report_date = (
            "" if pd.isna(source["ReportDate"]) else str(source["ReportDate"]).strip()
        )
        if (
            not ticker
            or rank is None
            or rank <= 0
            or score is None
            or not all(signals)
            or snapshot_status != "ACTIVE"
            or not report_date
        ):
            continue

        tone = research_tone(*signals)
        rows.append(
            {
                "Ticker": ticker,
                "Rank": rank,
                "CompositeScore": score,
                "TrendSignal": signals[0],
                "MomentumSignal": signals[1],
                "VolatilitySignal": signals[2],
                "ResearchTone": tone,
                "ResearchSummary": research_summary(tone),
                "ReportDate": report_date,
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def save_research_explanations(explanations, output_path=None):
    """Save explanations with their fixed field sequence."""
    if not isinstance(explanations, pd.DataFrame):
        raise TypeError("explanations must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    explanations.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_explanation_engine(input_path=None, output_path=None):
    """Load a snapshot, build explanations, and save the artifact."""
    snapshot = load_daily_snapshot(input_path)
    explanations = build_research_explanations(snapshot)
    path = save_research_explanations(explanations, output_path)
    tones = explanations["ResearchTone"].value_counts().to_dict()
    return {
        "explanations": explanations,
        "output_path": str(path),
        "summary": {
            "rows": int(len(explanations)),
            "positive": int(tones.get("POSITIVE", 0)),
            "neutral": int(tones.get("NEUTRAL", 0)),
            "caution": int(tones.get("CAUTION", 0)),
        },
    }


def main():
    try:
        result = run_explanation_engine()
    except (ValueError, TypeError, OSError) as error:
        print(f"Universe150 explanation error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 Research Explanations")
    print(f"Rows: {result['summary']['rows']}")
    print(f"Output: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
