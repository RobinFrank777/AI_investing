"""Merge Universe150 raw factor and risk research artifacts by ticker."""

import sys
from pathlib import Path

import pandas as pd

from research_schema import normalize_research_schema


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FACTOR_PATH = PROJECT_ROOT / "results" / "universe150_factor_raw.csv"
DEFAULT_RISK_PATH = PROJECT_ROOT / "results" / "universe150_risk_raw.csv"
DEFAULT_RANKING_PATH = PROJECT_ROOT / "results" / "universe150_factor_ranking.csv"
DEFAULT_SIGNAL_PATH = PROJECT_ROOT / "results" / "universe150_signal.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_raw.csv"
FACTOR_REQUIRED_COLUMNS = (
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
    "FactorStatus",
    "FactorError",
)
RISK_REQUIRED_COLUMNS = (
    "Ticker",
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
    "ObservationCount",
    "Status",
)
RISK_METRIC_COLUMNS = (
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
    "ObservationCount",
)
RANKING_REQUIRED_COLUMNS = (
    "Ticker",
    "TrendScore",
    "MomentumScore",
    "LowVolScore",
    "CompositeScore",
    "Rank",
)
SIGNAL_REQUIRED_COLUMNS = (
    "Ticker",
    "TrendSignal",
    "MomentumSignal",
    "VolatilitySignal",
    "CompositeSignal",
)
ALLOWED_STATUSES = frozenset({"PASS", "PARTIAL", "FAILED"})


def _load_csv(path, label):
    if not path.is_file():
        raise FileNotFoundError(f"Universe150 {label} file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Universe150 {label} file is empty: {path}") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"Universe150 {label} file is invalid: {path}") from error


def load_factor_data(input_path=None):
    """Load the raw factor artifact."""
    path = DEFAULT_FACTOR_PATH if input_path is None else Path(input_path)
    return _load_csv(path, "factor data")


def load_risk_data(input_path=None):
    """Load the raw risk artifact."""
    path = DEFAULT_RISK_PATH if input_path is None else Path(input_path)
    return _load_csv(path, "risk data")


def load_ranking_data(input_path=None):
    """Load the saved factor-ranking artifact."""
    path = DEFAULT_RANKING_PATH if input_path is None else Path(input_path)
    return _load_csv(path, "factor ranking")


def load_signal_data(input_path=None):
    """Load the saved research-signal artifact."""
    path = DEFAULT_SIGNAL_PATH if input_path is None else Path(input_path)
    return _load_csv(path, "signal data")


def _validate_columns(frame, required, label):
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{label} must be a pandas DataFrame")
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError(f"{label} is missing required columns: " + ", ".join(missing))
    duplicated = frame["Ticker"].fillna("").astype(str).str.strip().duplicated(keep=False)
    if duplicated.any():
        tickers = sorted(frame.loc[duplicated, "Ticker"].astype(str).unique())
        raise ValueError(f"{label} contains duplicate Ticker values: " + ", ".join(tickers))


def _status(value):
    normalized = str(value).strip().upper() if pd.notna(value) else "FAILED"
    return normalized if normalized in ALLOWED_STATUSES else "FAILED"


def _research_status(factor_status, risk_status):
    if factor_status == "PASS" and risk_status == "PASS":
        return "PASS"
    if factor_status == "FAILED" and risk_status == "FAILED":
        return "FAILED"
    return "PARTIAL"


def merge_risk_and_factor(factors, risk):
    """Left-join risk onto factors while preserving factor rows and order."""
    _validate_columns(factors, FACTOR_REQUIRED_COLUMNS, "factor data")
    _validate_columns(risk, RISK_REQUIRED_COLUMNS, "risk data")

    factor_source = factors.copy(deep=True)
    factor_source["Ticker"] = factor_source["Ticker"].fillna("").astype(str).str.strip()
    factor_source["FactorStatus"] = factor_source["FactorStatus"].map(_status)
    risk_source = risk.loc[:, RISK_REQUIRED_COLUMNS].copy(deep=True)
    risk_source["Ticker"] = risk_source["Ticker"].fillna("").astype(str).str.strip()
    risk_source = risk_source.rename(columns={"Status": "RiskStatus"})

    merged = factor_source.merge(
        risk_source,
        on="Ticker",
        how="left",
        sort=False,
        validate="one_to_one",
    )
    merged["RiskStatus"] = merged["RiskStatus"].map(_status)
    merged["ResearchStatus"] = [
        _research_status(factor_status, risk_status)
        for factor_status, risk_status in zip(
            merged["FactorStatus"], merged["RiskStatus"]
        )
    ]
    output_columns = (
        list(factor_source.columns)
        + list(RISK_METRIC_COLUMNS)
        + ["RiskStatus", "ResearchStatus"]
    )
    return merged.loc[:, output_columns]


def merge_research_artifacts(factors, risk, ranking, signals):
    """Merge raw, ranked, signal, and risk artifacts without recalculation."""
    _validate_columns(factors, FACTOR_REQUIRED_COLUMNS, "factor data")
    _validate_columns(risk, RISK_REQUIRED_COLUMNS, "risk data")
    _validate_columns(ranking, RANKING_REQUIRED_COLUMNS, "factor ranking")
    normalized_signals = normalize_research_schema(signals)
    _validate_columns(normalized_signals, SIGNAL_REQUIRED_COLUMNS, "signal data")

    factor_source = factors.copy(deep=True)
    factor_source["Ticker"] = factor_source["Ticker"].fillna("").astype(str).str.strip()
    factor_source["FactorStatus"] = factor_source["FactorStatus"].map(_status)

    ranking_source = ranking.loc[:, RANKING_REQUIRED_COLUMNS].copy(deep=True)
    ranking_source["Ticker"] = ranking_source["Ticker"].fillna("").astype(str).str.strip()

    signal_columns = (*SIGNAL_REQUIRED_COLUMNS, "Signal")
    signal_source = normalized_signals.loc[:, signal_columns].copy(deep=True)
    signal_source["Ticker"] = signal_source["Ticker"].fillna("").astype(str).str.strip()

    risk_source = risk.loc[:, RISK_REQUIRED_COLUMNS].copy(deep=True)
    risk_source["Ticker"] = risk_source["Ticker"].fillna("").astype(str).str.strip()
    risk_source = risk_source.rename(columns={"Status": "RiskStatus"})

    merged = factor_source.merge(
        ranking_source, on="Ticker", how="left", sort=False, validate="one_to_one"
    )
    merged = merged.merge(
        signal_source, on="Ticker", how="left", sort=False, validate="one_to_one"
    )
    merged = merged.merge(
        risk_source, on="Ticker", how="left", sort=False, validate="one_to_one"
    )
    merged["RiskStatus"] = merged["RiskStatus"].map(_status)
    merged["ResearchStatus"] = [
        _research_status(factor_status, risk_status)
        for factor_status, risk_status in zip(
            merged["FactorStatus"], merged["RiskStatus"]
        )
    ]
    output_columns = (
        list(factor_source.columns)
        + list(RANKING_REQUIRED_COLUMNS[1:])
        + list(SIGNAL_REQUIRED_COLUMNS[1:])
        + ["Signal"]
        + list(RISK_METRIC_COLUMNS)
        + ["RiskStatus", "ResearchStatus"]
    )
    return merged.loc[:, output_columns]


def save_research_raw(research, output_path=None):
    """Save an already-merged Universe150 research table without an index."""
    if not isinstance(research, pd.DataFrame):
        raise TypeError("research must be a pandas DataFrame")
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    research.to_csv(path, index=False)
    return path


def run_risk_factor_merge(factor_path=None, risk_path=None, output_path=None):
    """Load, merge, and save the Universe150 raw research artifact."""
    factors = load_factor_data(factor_path)
    risk = load_risk_data(risk_path)
    artifact_root = (
        DEFAULT_FACTOR_PATH.parent if factor_path is None else Path(factor_path).parent
    )
    ranking = load_ranking_data(artifact_root / DEFAULT_RANKING_PATH.name)
    signals = load_signal_data(artifact_root / DEFAULT_SIGNAL_PATH.name)
    research = merge_research_artifacts(factors, risk, ranking, signals)
    path = save_research_raw(research, output_path)
    counts = research["ResearchStatus"].value_counts().to_dict()
    return {
        "research": research,
        "output_path": str(path),
        "summary": {
            "total": int(len(research)),
            "pass": int(counts.get("PASS", 0)),
            "partial": int(counts.get("PARTIAL", 0)),
            "failed": int(counts.get("FAILED", 0)),
        },
    }


def main():
    try:
        result = run_risk_factor_merge()
    except (FileNotFoundError, ValueError, TypeError, OSError) as error:
        print(f"Universe150 risk-factor merge error: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print("AI_investing Universe150 Raw Research")
    print(f"Total: {summary['total']}")
    print(f"PASS: {summary['pass']}")
    print(f"PARTIAL: {summary['partial']}")
    print(f"FAILED: {summary['failed']}")
    print(f"Output: {result['output_path']}")
    print("Research data merge only; no execution workflow was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
