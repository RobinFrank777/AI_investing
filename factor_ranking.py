"""Cross-sectional research ranking for Universe150 raw price factors."""

import sys
from pathlib import Path

import pandas as pd

from factor_composite import validate_factor_weights
from factor_normalization import normalize_factor_series


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_factor_raw.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_factor_ranking.csv"
REQUIRED_RAW_COLUMNS = (
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
)
RANKING_COLUMNS = (
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
    "TrendScore",
    "MomentumScore",
    "LowVolScore",
    "CompositeScore",
    "Rank",
)


def load_raw_factors(input_path=None):
    """Load the Universe150 raw-factor artifact."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Universe150 raw factor file not found: {path}")
    try:
        raw = pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Universe150 raw factor file is empty: {path}") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"Universe150 raw factor file is invalid: {path}") from error
    if raw.empty:
        raise ValueError(f"Universe150 raw factor file contains no rows: {path}")
    return raw


def build_factor_ranking(raw):
    """Normalize native factors and calculate the fixed-weight composite rank."""
    if not isinstance(raw, pd.DataFrame):
        raise TypeError("raw factors must be a pandas DataFrame")
    missing = [column for column in REQUIRED_RAW_COLUMNS if column not in raw]
    if missing:
        raise ValueError("raw factors are missing required columns: " + ", ".join(missing))
    if raw.empty:
        raise ValueError("raw factors contain no rows")

    result = raw.loc[:, REQUIRED_RAW_COLUMNS].copy(deep=True)
    result["TrendScore"] = normalize_factor_series(
        result["TrendValue"], higher_is_better=True
    )
    result["MomentumScore"] = normalize_factor_series(
        result["MomentumValue"], higher_is_better=True
    )
    result["LowVolScore"] = normalize_factor_series(
        result["Volatility20D"], higher_is_better=False
    )

    weights = validate_factor_weights()["effective_weights"]
    complete = result[["TrendScore", "MomentumScore", "LowVolScore"]].notna().all(axis=1)
    result["CompositeScore"] = pd.Series(float("nan"), index=result.index)
    result.loc[complete, "CompositeScore"] = (
        result.loc[complete, "TrendScore"] * weights["TrendPercentile"]
        + result.loc[complete, "MomentumScore"] * weights["MomentumPercentile"]
        + result.loc[complete, "LowVolScore"] * weights["LowVolatilityPercentile"]
    )
    result["Rank"] = result["CompositeScore"].rank(
        method="average", ascending=False
    )
    return result.loc[:, RANKING_COLUMNS]


def save_factor_ranking(ranking, output_path=None):
    """Save an already-built Universe150 factor ranking without an index."""
    if not isinstance(ranking, pd.DataFrame):
        raise TypeError("ranking must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(path, index=False)
    return path


def run_factor_ranking(input_path=None, output_path=None):
    """Load raw factors, build the ranking, and save the research artifact."""
    raw = load_raw_factors(input_path)
    ranking = build_factor_ranking(raw)
    path = save_factor_ranking(ranking, output_path)
    ranked_count = int(ranking["Rank"].notna().sum())
    return {
        "ranking": ranking,
        "output_path": str(path),
        "summary": {
            "total": int(len(ranking)),
            "ranked": ranked_count,
            "unranked": int(len(ranking) - ranked_count),
        },
    }


def main():
    try:
        result = run_factor_ranking()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 factor ranking error: {error}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("AI_investing Universe150 Factor Ranking")
    print(f"Total: {summary['total']}")
    print(f"Ranked: {summary['ranked']}")
    print(f"Unranked: {summary['unranked']}")
    print(f"Output: {result['output_path']}")
    print("Research ranking only; no portfolio or trading action was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
