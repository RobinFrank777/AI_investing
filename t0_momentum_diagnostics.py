"""Offline correctness diagnostics for the production momentum score."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from config import PRIMARY_UNIVERSE_VERSION
from score_threshold_analysis import build_historical_score_table
from trade_signal import generate_signals


PROJECT_ROOT = Path(__file__).resolve().parent
DISTRIBUTION_OUTPUT = PROJECT_ROOT / "results" / "t0_momentum_contribution_distribution.csv"
SENSITIVITY_OUTPUT = PROJECT_ROOT / "results" / "t0_momentum_sensitivity_summary.csv"
SCENARIOS = ("Production", "Without MACD", "Without Return Momentum")
DIAGNOSTIC_COLUMNS = (
    "Date", "Ticker", "UniverseVersion", "MomentumScore",
    "ReturnMomentumContribution", "MACDContribution", "TechnicalScore",
    "FinalScore", "TradeSignal", "Volume_Ratio", "DistanceToHigh",
    "Close", "MA20", "MA60",
)


def contribution_shares(frame):
    """Use absolute-magnitude shares; zero-total rows remain explicitly N/A."""
    result = frame.copy(deep=True)
    denominator = (
        result["ReturnMomentumContribution"].abs()
        + result["MACDContribution"].abs()
    )
    valid = denominator > 0
    result["ReturnShare"] = np.nan
    result["MACDShare"] = np.nan
    result.loc[valid, "ReturnShare"] = (
        result.loc[valid, "ReturnMomentumContribution"].abs()
        / denominator.loc[valid]
    )
    result.loc[valid, "MACDShare"] = (
        result.loc[valid, "MACDContribution"].abs() / denominator.loc[valid]
    )
    return result


def dominance_warning(shares):
    valid = shares.dropna(subset=["ReturnShare", "MACDShare"])
    if valid.empty:
        return False
    return bool(
        valid["MACDShare"].median() > 0.75
        and valid["ReturnShare"].median() < 0.20
    )


def distribution_summary(frame, columns):
    quantiles = (0.10, 0.25, 0.50, 0.75, 0.90)
    rows = []
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        row = {
            "Metric": column, "count": int(values.count()),
            "mean": values.mean(), "median": values.median(),
            "std": values.std(ddof=1), "min": values.min(), "max": values.max(),
        }
        row.update({f"p{int(q * 100)}": values.quantile(q) for q in quantiles})
        rows.append(row)
    return pd.DataFrame(rows)[
        ["Metric", "count", "mean", "median", "std", "min", "p10", "p25", "p50", "p75", "p90", "max"]
    ]


def apply_sensitivity(production, scenario):
    """Recalculate an offline scenario without mutating production inputs."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    result = production.copy(deep=True)
    removed = pd.Series(0.0, index=result.index)
    if scenario == "Without MACD":
        removed = result["MACDContribution"]
    elif scenario == "Without Return Momentum":
        removed = result["ReturnMomentumContribution"]
    result["ScenarioTechnicalScore"] = result["TechnicalScore"] - 0.25 * removed
    result["ScenarioFinalScore"] = result["FinalScore"] - 0.70 * 0.25 * removed
    signal_input = result.rename(columns={"ScenarioFinalScore": "_ScenarioFinalScore"})
    signal_input["FinalScore"] = signal_input["_ScenarioFinalScore"]
    result["ScenarioTradeSignal"] = generate_signals(signal_input)["TradeSignal"]
    return result


def _top_members(group, score_column, fraction=None, count=None):
    size = count if count is not None else max(1, math.ceil(len(group) * fraction))
    return set(
        group.sort_values([score_column, "Ticker"], ascending=[False, True], kind="mergesort")
        .head(min(size, len(group)))["Ticker"]
    )


def sensitivity_summary(production):
    rows = []
    production_buy = int((production["TradeSignal"] == "BUY").sum())
    production_watch = int((production["TradeSignal"] == "WATCH").sum())
    for scenario in SCENARIOS:
        compared = apply_sensitivity(production, scenario)
        daily_correlations = []
        decile_overlaps = []
        top20_overlaps = []
        for _, group in compared.groupby("Date", sort=True):
            production_rank = group["FinalScore"].rank(method="average")
            scenario_rank = group["ScenarioFinalScore"].rank(method="average")
            correlation = production_rank.corr(scenario_rank)
            if pd.notna(correlation):
                daily_correlations.append(correlation)
            production_decile = _top_members(group, "FinalScore", fraction=0.10)
            scenario_decile = _top_members(group, "ScenarioFinalScore", fraction=0.10)
            decile_overlaps.append(len(production_decile & scenario_decile) / len(production_decile))
            production_top20 = _top_members(group, "FinalScore", count=20)
            scenario_top20 = _top_members(group, "ScenarioFinalScore", count=20)
            top20_overlaps.append(len(production_top20 & scenario_top20) / len(production_top20))
        rows.append({
            "Scenario": scenario,
            "RankCorrelation": float(np.mean(daily_correlations)),
            "TopDecileOverlap": float(np.mean(decile_overlaps)),
            "Top20Overlap": float(np.mean(top20_overlaps)),
            "BuyCountChange": int((compared["ScenarioTradeSignal"] == "BUY").sum()) - production_buy,
            "WatchCountChange": int((compared["ScenarioTradeSignal"] == "WATCH").sum()) - production_watch,
            "SignalChanges": int((compared["ScenarioTradeSignal"] != compared["TradeSignal"]).sum()),
            "TechnicalScoreMedianChange": float((compared["ScenarioTechnicalScore"] - compared["TechnicalScore"]).median()),
            "FinalScoreMedianChange": float((compared["ScenarioFinalScore"] - compared["FinalScore"]).median()),
        })
    return pd.DataFrame(rows)


def build_diagnostics(tickers):
    historical = build_historical_score_table(tickers=tickers)
    diagnostics = historical.copy()
    diagnostics["UniverseVersion"] = PRIMARY_UNIVERSE_VERSION
    diagnostics["TechnicalScore"] = diagnostics["Score"]
    diagnostics["TradeSignal"] = generate_signals(diagnostics.copy())["TradeSignal"]
    diagnostics = diagnostics.loc[:, DIAGNOSTIC_COLUMNS].copy()
    diagnostics["Date"] = pd.to_datetime(diagnostics["Date"]).dt.date.astype(str)
    return diagnostics


def save_diagnostics(diagnostics, distribution_output=DISTRIBUTION_OUTPUT, sensitivity_output=SENSITIVITY_OUTPUT):
    distribution_path = Path(distribution_output)
    sensitivity_path = Path(sensitivity_output)
    distribution_path.parent.mkdir(parents=True, exist_ok=True)
    sensitivity_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(distribution_path, index=False)
    summary = sensitivity_summary(diagnostics)
    summary.to_csv(sensitivity_path, index=False)
    return summary
