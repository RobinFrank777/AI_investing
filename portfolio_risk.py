"""Build a risk-ready model portfolio with fail-safe allocation boundaries."""

import numpy as np
import pandas as pd

from config import (
    MAX_HOLDINGS,
    MAX_SINGLE_POSITION_WEIGHT,
    MAX_TOTAL_EXPOSURE,
    LOW_RISK_WEIGHT_MULTIPLIER,
    MEDIUM_RISK_WEIGHT_MULTIPLIER,
    HIGH_RISK_WEIGHT_MULTIPLIER,
    UNKNOWN_RISK_WEIGHT_MULTIPLIER,
    MODEL_PORTFOLIO_OUTPUT_PATH,
    PRIMARY_UNIVERSE_VERSION,
    display_path,
)
from portfolio_risk_calculator import (
    DEFAULT_OUTPUT_PATH as PRODUCTION_RISK_INPUT_PATH,
    RISK_MODEL_VERSION,
    load_production_risk_inputs,
)


PRODUCTION_RISK_INPUT = PRODUCTION_RISK_INPUT_PATH
MODEL_PORTFOLIO_OUTPUT = MODEL_PORTFOLIO_OUTPUT_PATH
MAX_POSITION_WEIGHT = MAX_SINGLE_POSITION_WEIGHT
ALLOCATION_TOLERANCE = 1e-12

NO_QUALIFIED_CANDIDATES = "NO_QUALIFIED_CANDIDATES"
NO_RISK_READY_CANDIDATES = "NO_RISK_READY_CANDIDATES"
NO_SIZABLE_POSITIONS = "NO_SIZABLE_POSITIONS"
PRODUCTION_RISK_INPUTS_MISSING = "PRODUCTION_RISK_INPUTS_MISSING_NO_ACTION"
PRODUCTION_RISK_INPUTS_INCOMPATIBLE = "PRODUCTION_RISK_INPUTS_INCOMPATIBLE_NO_ACTION"
PORTFOLIO_READY = "PORTFOLIO_READY"

RISK_LEVEL_WEIGHT_MULTIPLIERS = {
    "Low": LOW_RISK_WEIGHT_MULTIPLIER,
    "Medium": MEDIUM_RISK_WEIGHT_MULTIPLIER,
    "High": HIGH_RISK_WEIGHT_MULTIPLIER,
    "Unknown": UNKNOWN_RISK_WEIGHT_MULTIPLIER,
}

PORTFOLIO_COLUMNS = (
    "Ticker",
    "RunId",
    "AsOfDate",
    "UniverseVersion",
    "ScoreModelVersion",
    "RiskModelVersion",
    "CandidateRank",
    "FinalScore",
    "BacktestScore",
    "TradeSignal",
    "Eligibility",
    "PortfolioEligible",
    "RiskStatus",
    "RiskReadyForPortfolio",
    "LatestClose",
    "LatestCloseAsOf",
    "MaxDrawdown",
    "SharpeRatio",
    "RiskLevel",
    "RiskReady",
    "RiskWeightMultiplier",
    "TargetWeight",
    "TargetWeightPercent",
    "PortfolioRole",
    "PortfolioStatus",
)


def _empty_portfolio(status):
    result = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    result.attrs["PortfolioStatus"] = status
    return result


def load_qualified_candidates():
    """Load the sole production risk-input authority; never use fallback."""
    try:
        source = load_production_risk_inputs(PRODUCTION_RISK_INPUT)
    except FileNotFoundError:
        return _empty_portfolio(PRODUCTION_RISK_INPUTS_MISSING)
    except (TypeError, ValueError):
        return _empty_portfolio(PRODUCTION_RISK_INPUTS_INCOMPATIBLE)
    if source.empty:
        return _empty_portfolio(NO_QUALIFIED_CANDIDATES)
    try:
        return _validate_production_risk_inputs(source)
    except (TypeError, ValueError):
        return _empty_portfolio(PRODUCTION_RISK_INPUTS_INCOMPATIBLE)


def assign_risk_level(row):
    """Classify only finite, formally usable drawdown and Sharpe inputs."""
    try:
        max_drawdown = float(row["MaxDrawdown"])
        sharpe_ratio = float(row["SharpeRatio"])
    except (KeyError, TypeError, ValueError):
        return "Unknown"
    if not np.isfinite(max_drawdown) or not np.isfinite(sharpe_ratio):
        return "Unknown"
    if max_drawdown >= -0.10 and sharpe_ratio >= 2:
        return "Low"
    if max_drawdown >= -0.25 and sharpe_ratio >= 1:
        return "Medium"
    return "High"


def get_risk_weight_multiplier(risk_level):
    return RISK_LEVEL_WEIGHT_MULTIPLIERS.get(
        risk_level, RISK_LEVEL_WEIGHT_MULTIPLIERS["Unknown"]
    )


def _prepare_candidates(candidates):
    required = {
        "Ticker", "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
        "RiskModelVersion", "CandidateRank", "FinalScore", "TradeSignal",
        "Eligibility", "PortfolioEligible", "MaxDrawdown", "SharpeRatio",
        "RiskLevel", "RiskWeightMultiplier", "RiskStatus",
        "RiskReadyForPortfolio", "LatestClose", "LatestCloseAsOf",
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError("qualified candidates missing columns: " + ", ".join(missing))
    prepared = candidates.copy(deep=True)
    prepared["Ticker"] = prepared["Ticker"].fillna("").astype(str).str.strip().str.upper()
    for column in (
        "CandidateRank", "FinalScore", "MaxDrawdown", "SharpeRatio",
        "RiskWeightMultiplier", "LatestClose",
    ):
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    for column in ("PortfolioEligible", "RiskReadyForPortfolio"):
        values = prepared[column]
        if values.dtype != bool:
            values = values.astype(str).str.strip().str.upper().map(
                {"TRUE": True, "FALSE": False}
            )
        prepared[column] = values.fillna(False).astype(bool)
    prepared["RiskReady"] = (
        prepared["Ticker"].ne("")
        & prepared["PortfolioEligible"]
        & prepared["RiskReadyForPortfolio"]
        & prepared["RiskStatus"].eq("RISK_READY")
        & np.isfinite(prepared["FinalScore"])
        & np.isfinite(prepared["MaxDrawdown"])
        & np.isfinite(prepared["SharpeRatio"])
        & prepared["RiskLevel"].isin({"Low", "Medium", "High"})
        & np.isfinite(prepared["RiskWeightMultiplier"])
        & prepared["RiskWeightMultiplier"].gt(0)
    )
    if "BacktestScore" not in prepared:
        prepared["BacktestScore"] = prepared["FinalScore"]
    return prepared


def _single(frame, column):
    values = frame[column].fillna("").astype(str).str.strip()
    if values.eq("").any() or values.nunique(dropna=False) != 1:
        raise ValueError(f"production risk inputs contain missing or mixed {column}")
    return values


def _validate_production_risk_inputs(source):
    prepared = _prepare_candidates(source)
    for column in (
        "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
        "RiskModelVersion",
    ):
        prepared[column] = _single(prepared, column)
    if prepared.UniverseVersion.iloc[0] != PRIMARY_UNIVERSE_VERSION:
        raise ValueError("production risk inputs contain incompatible UniverseVersion")
    if prepared.RiskModelVersion.iloc[0] != RISK_MODEL_VERSION:
        raise ValueError("production risk inputs contain incompatible RiskModelVersion")
    as_of = pd.to_datetime(prepared.AsOfDate, errors="raise")
    latest = pd.to_datetime(prepared.LatestCloseAsOf, errors="coerce")
    ready = prepared.RiskReadyForPortfolio
    if latest.loc[ready].isna().any() or (latest.loc[ready] > as_of.loc[ready]).any():
        raise ValueError("production risk inputs contain incompatible LatestCloseAsOf")
    if prepared.Ticker.duplicated().any():
        raise ValueError("production risk inputs contain duplicate Ticker")
    return prepared


def build_model_portfolio(candidates_df=None):
    """Filter risk readiness before selection, then allocate within hard caps."""
    candidates = load_qualified_candidates() if candidates_df is None else candidates_df
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("qualified candidates must be a pandas DataFrame")
    if candidates.empty:
        status = candidates.attrs.get("PortfolioStatus", NO_QUALIFIED_CANDIDATES)
        return _empty_portfolio(status)

    if candidates_df is not None:
        try:
            prepared = _validate_production_risk_inputs(candidates)
        except (TypeError, ValueError):
            return _empty_portfolio(PRODUCTION_RISK_INPUTS_INCOMPATIBLE)
    else:
        prepared = _prepare_candidates(candidates)
    qualified_count = int(prepared.PortfolioEligible.sum())
    if qualified_count == 0:
        return _empty_portfolio(NO_QUALIFIED_CANDIDATES)
    eligible = prepared.loc[prepared["RiskReady"]].copy()
    if eligible.empty:
        return _empty_portfolio(NO_RISK_READY_CANDIDATES)

    excluded = prepared.loc[prepared.PortfolioEligible & ~prepared.RiskReady, ["Ticker", "RiskStatus"]]
    eligible = eligible.sort_values(
        ["FinalScore", "CandidateRank", "Ticker"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    selected = eligible.head(MAX_HOLDINGS).copy()

    multipliers = pd.to_numeric(selected["RiskWeightMultiplier"], errors="coerce")
    sizable = np.isfinite(multipliers) & (multipliers > 0)
    selected = selected.loc[sizable].copy()
    if selected.empty:
        return _empty_portfolio(NO_SIZABLE_POSITIONS)

    multiplier_sum = float(selected["RiskWeightMultiplier"].sum())
    if not np.isfinite(multiplier_sum) or multiplier_sum <= 0:
        return _empty_portfolio(NO_SIZABLE_POSITIONS)

    # MAX_TOTAL_EXPOSURE is a ceiling used to form base weights, never a fill
    # mandate. Capping a position may leave additional cash; no redistribution.
    base_weights = selected["RiskWeightMultiplier"] / multiplier_sum * MAX_TOTAL_EXPOSURE
    selected["TargetWeight"] = base_weights.clip(upper=MAX_POSITION_WEIGHT)
    weights = selected["TargetWeight"].to_numpy(dtype=float)
    if (
        not np.isfinite(weights).all()
        or (weights < 0).any()
        or (weights > MAX_POSITION_WEIGHT + ALLOCATION_TOLERANCE).any()
        or weights.sum() > MAX_TOTAL_EXPOSURE + ALLOCATION_TOLERANCE
    ):
        raise RuntimeError("portfolio allocation invariant violation")

    selected["TargetWeightPercent"] = (
        selected["TargetWeight"] * 100
    ).round(2).astype(str) + "%"
    selected["PortfolioRole"] = "candidate"
    selected["PortfolioStatus"] = PORTFOLIO_READY
    selected.attrs["PortfolioStatus"] = PORTFOLIO_READY
    selected.attrs["ExcludedRiskCandidates"] = excluded.to_dict("records")
    return selected


def save_model_portfolio(portfolio_df):
    MODEL_PORTFOLIO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    portfolio_df.to_csv(MODEL_PORTFOLIO_OUTPUT, index=False)
    return MODEL_PORTFOLIO_OUTPUT


def print_model_portfolio():
    portfolio_df = build_model_portfolio()
    status = portfolio_df.attrs.get("PortfolioStatus", PORTFOLIO_READY)
    print("=" * 70)
    print("MODEL PORTFOLIO")
    print("=" * 70)
    if portfolio_df.empty:
        print(f"Portfolio Status           : {status}")
    else:
        print(
            portfolio_df[
                ["Ticker", "FinalScore", "CandidateRank",
                 "MaxDrawdown", "SharpeRatio", "RiskLevel", "RiskReady",
                 "RiskWeightMultiplier", "TargetWeightPercent", "PortfolioRole"]
            ].to_string(index=False)
        )
    total_weight = float(portfolio_df["TargetWeight"].sum()) if "TargetWeight" in portfolio_df else 0.0
    output_path = save_model_portfolio(portfolio_df)
    print("\nPortfolio Summary")
    print(f"Portfolio Status           : {status}")
    print(f"Holdings Count             : {len(portfolio_df)}")
    print(f"Total Exposure             : {total_weight:.2%}")
    print(f"Cash / Unallocated Capital : {1 - total_weight:.2%}")
    print(f"Saved Model Portfolio To   : {display_path(output_path)}")


if __name__ == "__main__":
    print_model_portfolio()
