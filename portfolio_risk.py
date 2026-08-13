"""Build a risk-ready model portfolio with fail-safe allocation boundaries."""

from datetime import date
from pathlib import Path

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
    display_path,
)
from portfolio_candidate_adapter import (
    DEFAULT_INPUT_PATH as PRODUCTION_CANDIDATE_OUTPUT_PATH,
    build_validated_portfolio_candidates,
    load_production_candidates,
)
from production_candidate_builder import MAX_STALENESS_DAYS


PRODUCTION_CANDIDATE_OUTPUT = PRODUCTION_CANDIDATE_OUTPUT_PATH
MODEL_PORTFOLIO_OUTPUT = MODEL_PORTFOLIO_OUTPUT_PATH
MAX_POSITION_WEIGHT = MAX_SINGLE_POSITION_WEIGHT
ALLOCATION_TOLERANCE = 1e-12

NO_QUALIFIED_CANDIDATES = "NO_QUALIFIED_CANDIDATES"
NO_RISK_READY_CANDIDATES = "NO_RISK_READY_CANDIDATES"
NO_SIZABLE_POSITIONS = "NO_SIZABLE_POSITIONS"
PRODUCTION_CANDIDATES_MISSING = "PRODUCTION_CANDIDATES_MISSING_NO_ACTION"
PRODUCTION_CANDIDATES_EMPTY = "PRODUCTION_CANDIDATES_EMPTY_NO_ACTION"
PRODUCTION_CANDIDATES_STALE = "PRODUCTION_CANDIDATES_STALE_NO_ACTION"
PRODUCTION_CANDIDATES_INCOMPATIBLE = "PRODUCTION_CANDIDATES_INCOMPATIBLE_NO_ACTION"
PRODUCTION_RISK_INPUTS_NOT_READY = "PRODUCTION_RISK_INPUTS_NOT_READY_NO_ACTION"
PORTFOLIO_READY = "PORTFOLIO_READY"

RISK_LEVEL_WEIGHT_MULTIPLIERS = {
    "Low": LOW_RISK_WEIGHT_MULTIPLIER,
    "Medium": MEDIUM_RISK_WEIGHT_MULTIPLIER,
    "High": HIGH_RISK_WEIGHT_MULTIPLIER,
    "Unknown": UNKNOWN_RISK_WEIGHT_MULTIPLIER,
}

PORTFOLIO_COLUMNS = (
    "Ticker",
    "BacktestScore",
    "AverageReturn",
    "WinRate",
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
    """Load the sole production candidate authority; never use backtest fallback."""
    try:
        source = load_production_candidates(PRODUCTION_CANDIDATE_OUTPUT)
        validated = build_validated_portfolio_candidates(source)
    except FileNotFoundError:
        return _empty_portfolio(PRODUCTION_CANDIDATES_MISSING)
    except (TypeError, ValueError):
        return _empty_portfolio(PRODUCTION_CANDIDATES_INCOMPATIBLE)

    if validated.empty:
        return _empty_portfolio(PRODUCTION_CANDIDATES_EMPTY)

    try:
        as_of_date = pd.to_datetime(
            validated["AsOfDate"].iloc[0], errors="raise"
        ).date()
    except (TypeError, ValueError, OverflowError):
        return _empty_portfolio(PRODUCTION_CANDIDATES_INCOMPATIBLE)
    age = (date.today() - as_of_date).days
    if age < 0:
        return _empty_portfolio(PRODUCTION_CANDIDATES_INCOMPATIBLE)
    if age > MAX_STALENESS_DAYS:
        return _empty_portfolio(PRODUCTION_CANDIDATES_STALE)

    eligible = validated.loc[validated["PortfolioEligible"]].copy()
    if eligible.empty:
        return _empty_portfolio(PRODUCTION_CANDIDATES_EMPTY)

    # B1 removes legacy authority but does not force the pending production
    # candidate-to-risk allocation cutover. Until that contract is complete,
    # valid candidates fail closed instead of borrowing legacy backtest metrics.
    return _empty_portfolio(PRODUCTION_RISK_INPUTS_NOT_READY)


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
        "Ticker", "BacktestScore", "AverageReturn", "WinRate",
        "MaxDrawdown", "SharpeRatio",
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError("qualified candidates missing columns: " + ", ".join(missing))
    prepared = candidates.copy(deep=True)
    prepared["Ticker"] = prepared["Ticker"].fillna("").astype(str).str.strip().str.upper()
    for column in ("BacktestScore", "MaxDrawdown", "SharpeRatio"):
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    prepared["RiskLevel"] = prepared.apply(assign_risk_level, axis=1)
    prepared["RiskReady"] = (
        prepared["Ticker"].ne("")
        & np.isfinite(prepared["BacktestScore"])
        & prepared["RiskLevel"].ne("Unknown")
    )
    prepared["RiskWeightMultiplier"] = prepared["RiskLevel"].map(
        get_risk_weight_multiplier
    )
    return prepared


def build_model_portfolio(candidates_df=None):
    """Filter risk readiness before selection, then allocate within hard caps."""
    candidates = load_qualified_candidates() if candidates_df is None else candidates_df
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("qualified candidates must be a pandas DataFrame")
    if candidates.empty:
        status = candidates.attrs.get("PortfolioStatus", NO_QUALIFIED_CANDIDATES)
        return _empty_portfolio(status)

    prepared = _prepare_candidates(candidates)
    eligible = prepared.loc[prepared["RiskReady"]].copy()
    if eligible.empty:
        return _empty_portfolio(NO_RISK_READY_CANDIDATES)

    # BacktestScore remains the primary ranking authority. Ticker is only a
    # deterministic tie-break, applied after risk readiness filtering.
    eligible = eligible.sort_values(
        ["BacktestScore", "Ticker"],
        ascending=[False, True],
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
                ["Ticker", "BacktestScore", "AverageReturn", "WinRate",
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
