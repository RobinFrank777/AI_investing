"""Offline BUY-threshold governance diagnostics; production rules stay untouched."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import PRIMARY_UNIVERSE_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent
THRESHOLD_GRID = (60, 65, 70, 75, 80)
CURRENT_BUY_THRESHOLD = 75
CURRENT_WATCH_THRESHOLD = 60
SUMMARY_OUTPUT = PROJECT_ROOT / "results" / "t1_threshold_governance_summary.csv"
MONTHLY_OUTPUT = PROJECT_ROOT / "results" / "t1_threshold_monthly_distribution.csv"


def select_candidates(scores, threshold):
    """Apply a candidate threshold directly to FinalScore, not TradeSignal."""
    return scores.loc[scores["FinalScore"] >= threshold].copy()


def forward_return_statistics(values, prefix):
    valid = pd.to_numeric(values, errors="coerce").dropna()
    return {
        f"{prefix}SampleCount": int(len(valid)),
        f"{prefix}Mean": valid.mean(),
        f"{prefix}Median": valid.median(),
        f"{prefix}WinRate": (valid > 0).mean() if not valid.empty else np.nan,
        f"{prefix}P10": valid.quantile(0.10),
        f"{prefix}P25": valid.quantile(0.25),
        f"{prefix}P75": valid.quantile(0.75),
        f"{prefix}P90": valid.quantile(0.90),
    }


def monthly_distribution(scores, threshold, months=None):
    dates = pd.to_datetime(scores["Date"], errors="raise")
    if months is None:
        months = pd.period_range(dates.min(), dates.max(), freq="M") if len(dates) else []
    candidates = select_candidates(scores, threshold).copy()
    candidates["Month"] = pd.to_datetime(candidates["Date"]).dt.to_period("M")
    counts = candidates.groupby("Month").agg(
        BuyCount=("Ticker", "size"), UniqueTickerCount=("Ticker", "nunique")
    )
    month_index = pd.PeriodIndex(months, freq="M", name="Month")
    counts = counts.reindex(month_index, fill_value=0).reset_index()
    counts["Month"] = counts["Month"].astype(str)
    counts.insert(1, "Threshold", threshold)
    return counts.loc[:, ["Month", "Threshold", "BuyCount", "UniqueTickerCount"]]


def concentration_metrics(candidates):
    if candidates.empty:
        return {"Top1TickerShare": 0.0, "Top5TickerShare": 0.0, "HHI": 0.0}
    shares = candidates["Ticker"].value_counts(normalize=True)
    return {
        "Top1TickerShare": float(shares.iloc[0]),
        "Top5TickerShare": float(shares.head(5).sum()),
        "HHI": float((shares ** 2).sum()),
    }


def summarize_threshold(scores, threshold, eligible_count, months=None):
    candidates = select_candidates(scores, threshold)
    monthly = monthly_distribution(scores, threshold, months=months)
    total = len(candidates)
    unique = int(candidates["Ticker"].nunique())
    result = {
        "Threshold": threshold,
        "UniverseVersion": PRIMARY_UNIVERSE_VERSION,
        "TotalBuyObservations": int(total),
        "UniqueBuyTickers": unique,
        "CandidateCoverage": unique / eligible_count if eligible_count else 0.0,
        "CandidateFrequency": total / len(scores) if len(scores) else 0.0,
        "BuyObservationsPerMonth": total / len(monthly) if len(monthly) else 0.0,
        "MedianMonthlyBuyCount": float(monthly["BuyCount"].median()) if len(monthly) else 0.0,
        "ZeroBuyMonths": int((monthly["BuyCount"] == 0).sum()),
        "MaximumMonthlyBuyCount": int(monthly["BuyCount"].max()) if len(monthly) else 0,
    }
    result.update(concentration_metrics(candidates))
    if total:
        month_shares = candidates.assign(
            Month=pd.to_datetime(candidates["Date"]).dt.to_period("M")
        )["Month"].value_counts(normalize=True)
        result["TopMonthShare"] = float(month_shares.iloc[0])
    else:
        result["TopMonthShare"] = 0.0
    if "Sector" in candidates:
        sector = candidates["Sector"].fillna("UNKNOWN").value_counts(normalize=True)
        result["TopSectorShare"] = float(sector.iloc[0]) if len(sector) else 0.0
    else:
        result["TopSectorShare"] = np.nan
    for horizon in (5, 20, 60):
        result.update(
            forward_return_statistics(
                candidates[f"Forward{horizon}DReturn"], f"Return{horizon}D"
            )
        )
    return result, monthly


def build_governance_summary(scores, eligible_count, thresholds=THRESHOLD_GRID):
    if tuple(thresholds) != tuple(sorted(thresholds)):
        raise ValueError("thresholds must be sorted")
    if scores.empty:
        months = []
    else:
        dates = pd.to_datetime(scores["Date"], errors="raise")
        months = pd.period_range(dates.min(), dates.max(), freq="M")
    summaries = []
    monthly_tables = []
    for threshold in thresholds:
        summary, monthly = summarize_threshold(scores, threshold, eligible_count, months)
        summaries.append(summary)
        monthly_tables.append(monthly)
    return pd.DataFrame(summaries), pd.concat(monthly_tables, ignore_index=True) if monthly_tables else pd.DataFrame()


def adjacent_stability(summary):
    rows = []
    ordered = summary.sort_values("Threshold").reset_index(drop=True)
    for index in range(1, len(ordered)):
        previous, current = ordered.iloc[index - 1], ordered.iloc[index]
        row = {
            "Transition": f"{int(previous.Threshold)}→{int(current.Threshold)}",
            "CandidateCountChange": int(current.TotalBuyObservations - previous.TotalBuyObservations),
            "UniqueTickerChange": int(current.UniqueBuyTickers - previous.UniqueBuyTickers),
            "HHIChange": current.HHI - previous.HHI,
        }
        for horizon in (5, 20, 60):
            for metric in ("Median", "WinRate"):
                field = f"Return{horizon}D{metric}"
                row[f"{horizon}D{metric}Change"] = current[field] - previous[field]
        rows.append(row)
    return pd.DataFrame(rows)


def add_sector(scores, universe):
    """Attach existing authoritative sector metadata without changing rows."""
    mapping = universe.loc[:, ["ticker", "sector"]].copy()
    mapping.columns = ["Ticker", "Sector"]
    mapping["Ticker"] = mapping["Ticker"].astype(str).str.strip().str.upper()
    return scores.merge(mapping, on="Ticker", how="left", validate="many_to_one")


def save_outputs(summary, monthly, summary_output=SUMMARY_OUTPUT, monthly_output=MONTHLY_OUTPUT):
    summary_path, monthly_path = Path(summary_output), Path(monthly_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    monthly_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    return summary_path, monthly_path
