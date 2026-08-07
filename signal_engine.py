"""Convert saved Universe150 factor scores into descriptive research states."""

import math
import sys
from pathlib import Path

import pandas as pd

from factor_ranking import RANKING_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_factor_ranking.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_signal.csv"
REQUIRED_COLUMNS = tuple(RANKING_COLUMNS)
SIGNAL_COLUMNS = (
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "CompositeSignal",
)


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def trend_signal(value):
    """Classify the saved TrendScore."""
    score = _number(value)
    if score is None:
        return "UNKNOWN"
    if score >= 0.75:
        return "STRONG"
    if score >= 0.50:
        return "NORMAL"
    return "WEAK"


def momentum_signal(value):
    """Classify the saved MomentumScore."""
    score = _number(value)
    if score is None:
        return "UNKNOWN"
    if score >= 0.75:
        return "POSITIVE"
    if score >= 0.50:
        return "NEUTRAL"
    return "NEGATIVE"


def volatility_signal(value):
    """Classify LowVolScore so higher scores represent lower volatility."""
    score = _number(value)
    if score is None:
        return "UNKNOWN"
    if score >= 0.75:
        return "LOW"
    if score >= 0.50:
        return "NORMAL"
    return "HIGH"


def composite_signal(value):
    """Classify the saved CompositeScore into research grades."""
    score = _number(value)
    if score is None:
        return "UNKNOWN"
    if score >= 0.85:
        return "A"
    if score >= 0.70:
        return "B"
    if score >= 0.55:
        return "C"
    return "D"


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


def build_signals(ranking):
    """Append research-state columns without changing scores, ranks, or row order."""
    if not isinstance(ranking, pd.DataFrame):
        raise TypeError("ranking must be a pandas DataFrame")
    missing = [column for column in REQUIRED_COLUMNS if column not in ranking]
    if missing:
        raise ValueError(
            "factor ranking is missing required columns: " + ", ".join(missing)
        )

    result = ranking.copy(deep=True)
    result["TrendSignal"] = result["TrendScore"].map(trend_signal)
    result["MomentumSignal"] = result["MomentumScore"].map(momentum_signal)
    result["VolatilitySignal"] = result["LowVolScore"].map(volatility_signal)
    result["CompositeSignal"] = result["CompositeScore"].map(composite_signal)
    return result


def save_signals(signals, output_path=None):
    """Save an already-built Universe150 signal table without an index."""
    if not isinstance(signals, pd.DataFrame):
        raise TypeError("signals must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(path, index=False)
    return path


def run_signal_engine(input_path=None, output_path=None):
    """Load factor rankings, append research states, and save the artifact."""
    ranking = load_factor_ranking(input_path)
    signals = build_signals(ranking)
    path = save_signals(signals, output_path)
    return {
        "signals": signals,
        "output_path": str(path),
        "summary": {"rows": int(len(signals))},
    }


def main():
    try:
        result = run_signal_engine()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 signal engine error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Universe150 Research States")
    print(f"Rows: {result['summary']['rows']}")
    print(f"Output: {result['output_path']}")
    print("Descriptive research states only; no execution action was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
