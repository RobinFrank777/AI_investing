"""Robustness diagnostics for Phase 5 factor-validation outputs."""

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from config import DATA_DIR_PATH, RESULTS_DIR_PATH, display_path
from factor_validation import (
    GROUP_FRACTION, HORIZONS, build_group_return_table, build_rank_ic_table,
)
from stock_loader import load_stock
from universe_source import load_active_universe


TRIM_PROPORTION = 0.10
MIN_TRIM_COUNT = 10
DATE_CONCENTRATION_THRESHOLD = 0.50
SYMBOL_INFLUENCE_THRESHOLD = 0.02
ENTRY_IC_DIFFERENCE_THRESHOLD = 0.10
ENTRY_SPREAD_DIFFERENCE_THRESHOLD = 0.02
MIN_REGIME_DATES = 5
MEAN_MEDIAN_DISAGREEMENT = 0.02
OUTPUT_PATHS = {
    "date_contributions": RESULTS_DIR_PATH / "factor_validation_date_contributions.csv",
    "robust_stats": RESULTS_DIR_PATH / "factor_validation_robust_stats.csv",
    "symbol_influence": RESULTS_DIR_PATH / "factor_validation_symbol_influence.csv",
    "entry_comparison": RESULTS_DIR_PATH / "factor_validation_entry_comparison.csv",
    "regimes": RESULTS_DIR_PATH / "factor_validation_regimes.csv",
    "coverage": RESULTS_DIR_PATH / "factor_validation_coverage.csv",
}


def _clean(values):
    result = pd.to_numeric(values, errors="coerce").dropna()
    return result[result.map(math.isfinite)]


def _trimmed_mean(values):
    clean = _clean(values).sort_values().reset_index(drop=True)
    trim = math.floor(len(clean) * TRIM_PROPORTION)
    if len(clean) < MIN_TRIM_COUNT or trim == 0:
        return None
    kept = clean.iloc[trim:len(clean)-trim]
    return float(kept.mean()) if len(kept) else None


def _stats(values):
    clean = _clean(values)
    return {
        "ObservationCount": int(len(clean)),
        "Mean": float(clean.mean()) if len(clean) else None,
        "Median": float(clean.median()) if len(clean) else None,
        "TrimmedMean": _trimmed_mean(clean),
        "Std": float(clean.std(ddof=1)) if len(clean) >= 2 else None,
        "Min": float(clean.min()) if len(clean) else None,
        "Max": float(clean.max()) if len(clean) else None,
        "P25": float(clean.quantile(.25)) if len(clean) else None,
        "P75": float(clean.quantile(.75)) if len(clean) else None,
        "PositiveRatio": float((clean > 0).mean()) if len(clean) else None,
    }


def build_date_contribution_diagnostics(group_returns):
    rows = []
    for horizon in [f"{h}D" for h in HORIZONS]:
        subset = group_returns[group_returns.Horizon == horizon]
        top = subset[subset.Group == "Top"].set_index("RebalanceDate")["AverageForwardReturn"]
        bottom = subset[subset.Group == "Bottom"].set_index("RebalanceDate")["AverageForwardReturn"]
        dates = list(dict.fromkeys(subset.RebalanceDate))
        frame = pd.DataFrame({"RebalanceDate": dates})
        frame["Horizon"] = horizon
        frame["TopGroupReturn"] = frame.RebalanceDate.map(top)
        frame["BottomGroupReturn"] = frame.RebalanceDate.map(bottom)
        frame["LongShortSpread"] = frame.TopGroupReturn - frame.BottomGroupReturn
        rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def summarize_date_contributions(date_contributions):
    result = {}
    for horizon in [f"{h}D" for h in HORIZONS]:
        frame = date_contributions[date_contributions.Horizon == horizon].dropna(subset=["LongShortSpread"])
        values = frame.LongShortSpread
        total = values.sum()
        ordered = frame.sort_values("LongShortSpread", ascending=False, kind="mergesort")
        best = ordered.iloc[0] if len(ordered) else None
        worst = ordered.iloc[-1] if len(ordered) else None
        result[horizon] = {
            **_stats(values),
            "BestDate": best.RebalanceDate if best is not None else None,
            "WorstDate": worst.RebalanceDate if worst is not None else None,
            "BestDateContribution": float(best.LongShortSpread / total) if best is not None and abs(total) > 1e-15 else None,
            "BestThreeContribution": float(ordered.head(3).LongShortSpread.sum() / total) if len(ordered) and abs(total) > 1e-15 else None,
            "MeanExcludingBest": float(ordered.iloc[1:].LongShortSpread.mean()) if len(ordered) > 1 else None,
            "MeanExcludingWorst": float(ordered.iloc[:-1].LongShortSpread.mean()) if len(ordered) > 1 else None,
        }
    return result


def build_robust_return_statistics(group_returns):
    rows = []
    for horizon in [f"{h}D" for h in HORIZONS]:
        subset = group_returns[group_returns.Horizon == horizon]
        for name in ("Top", "Middle", "Bottom"):
            values = subset[subset.Group == name].AverageForwardReturn
            rows.append({"Horizon": horizon, "Series": name, **_stats(values)})
        spreads = subset[subset.Group == "Top"].LongShortSpread
        rows.append({"Horizon": horizon, "Series": "Top-Bottom", **_stats(spreads)})
    return pd.DataFrame(rows)


def _memberships(validation):
    memberships = []
    for date in validation.RebalanceDate.drop_duplicates():
        frame = validation[validation.RebalanceDate == date].copy()
        frame["_order"] = range(len(frame))
        frame = frame.dropna(subset=["CompositeFactorScore"]).sort_values(
            ["CompositeFactorScore", "_order"], ascending=[False, True], kind="mergesort"
        )
        size = max(1, math.ceil(len(frame) * GROUP_FRACTION)) if len(frame) else 0
        for group, selected in (("Top", frame.head(size)), ("Bottom", frame.tail(size))):
            for _, row in selected.iterrows():
                memberships.append({"RebalanceDate": date, "Ticker": row.Ticker, "Group": group, **{
                    f"ForwardReturn{h}D": row[f"ForwardReturn{h}D"] for h in HORIZONS
                }})
    return pd.DataFrame(memberships)


def build_symbol_influence_table(validation_table):
    members = _memberships(validation_table)
    symbols = validation_table.Ticker.drop_duplicates().tolist()
    rows = []
    for horizon in HORIZONS:
        field = f"ForwardReturn{horizon}D"
        top_all = _clean(members[members.Group == "Top"][field])
        bottom_all = _clean(members[members.Group == "Bottom"][field])
        baseline = top_all.mean() - bottom_all.mean() if len(top_all) and len(bottom_all) else None
        for ticker in symbols:
            top = _clean(members[(members.Ticker == ticker) & (members.Group == "Top")][field])
            bottom = _clean(members[(members.Ticker == ticker) & (members.Group == "Bottom")][field])
            remaining_top = _clean(members[(members.Ticker != ticker) & (members.Group == "Top")][field])
            remaining_bottom = _clean(members[(members.Ticker != ticker) & (members.Group == "Bottom")][field])
            excluded = remaining_top.mean() - remaining_bottom.mean() if len(remaining_top) and len(remaining_bottom) else None
            rows.append({
                "Ticker": ticker, "Horizon": f"{horizon}D",
                "TopAppearances": int(((members.Ticker == ticker) & (members.Group == "Top")).sum()),
                "BottomAppearances": int(((members.Ticker == ticker) & (members.Group == "Bottom")).sum()),
                "TopForwardReturnMean": float(top.mean()) if len(top) else None,
                "BottomForwardReturnMean": float(bottom.mean()) if len(bottom) else None,
                "TopReturnContribution": float(top.sum() / len(top_all)) if len(top_all) else None,
                "BottomReturnContribution": float(bottom.sum() / len(bottom_all)) if len(bottom_all) else None,
                "BaselineMeanSpread": float(baseline) if baseline is not None else None,
                "MeanSpreadExcludingSymbol": float(excluded) if excluded is not None else None,
                "SpreadChange": float(excluded - baseline) if excluded is not None and baseline is not None else None,
            })
    return pd.DataFrame(rows)


def calculate_next_close_return(data, rebalance_date, horizon):
    frame = data.copy(deep=True)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame.dropna(subset=["Date", "Close"]).sort_values("Date", kind="mergesort").reset_index(drop=True)
    cutoff = pd.to_datetime(rebalance_date, errors="raise")
    future = frame.index[frame.Date > cutoff]
    if len(future) == 0:
        return None
    entry_index = int(future[0]); exit_index = entry_index + horizon
    if exit_index >= len(frame) or frame.at[entry_index, "Close"] == 0:
        return None
    value = float(frame.at[exit_index, "Close"] / frame.at[entry_index, "Close"] - 1)
    return value if math.isfinite(value) else None


def build_alternative_entry_validation(validation_table, market_data):
    result = validation_table.copy(deep=True)
    for index, row in result.iterrows():
        for horizon in HORIZONS:
            try:
                value = calculate_next_close_return(market_data[row.Ticker], row.RebalanceDate, horizon)
            except (KeyError, ValueError, TypeError):
                value = None
            result.at[index, f"ForwardReturn{horizon}D"] = value
    return result


def build_entry_comparison(same_close, next_close):
    same_ic, next_ic = build_rank_ic_table(same_close), build_rank_ic_table(next_close)
    same_groups, next_groups = build_group_return_table(same_close), build_group_return_table(next_close)
    rows = []
    for horizon in [f"{h}D" for h in HORIZONS]:
        sic = _clean(same_ic[same_ic.Horizon == horizon].RankIC).mean()
        nic = _clean(next_ic[next_ic.Horizon == horizon].RankIC).mean()
        ss = _clean(same_groups[(same_groups.Horizon == horizon) & (same_groups.Group == "Top")].LongShortSpread).mean()
        ns = _clean(next_groups[(next_groups.Horizon == horizon) & (next_groups.Group == "Top")].LongShortSpread).mean()
        rows.append({"Horizon": horizon, "SameCloseMeanIC": sic, "NextCloseMeanIC": nic,
                     "SameCloseMeanSpread": ss, "NextCloseMeanSpread": ns,
                     "ICDifference": nic-sic, "SpreadDifference": ns-ss})
    return pd.DataFrame(rows)


def classify_market_regimes(rebalance_dates, benchmark_data):
    if benchmark_data is None:
        return pd.DataFrame({"RebalanceDate": rebalance_dates, "Regime": "Unavailable"})
    frame = benchmark_data.copy(deep=True); frame["Date"] = pd.to_datetime(frame.Date, errors="coerce")
    frame["Close"] = pd.to_numeric(frame.Close, errors="coerce"); frame = frame.dropna(subset=["Date", "Close"]).sort_values("Date")
    rows = []
    for date in rebalance_dates:
        cutoff = pd.to_datetime(date); history = frame[frame.Date <= cutoff]
        regime = "Unavailable"
        if len(history) >= 60:
            regime = "Risk-On" if history.Close.iloc[-1] >= history.Close.iloc[-60:].mean() else "Risk-Off"
        rows.append({"RebalanceDate": str(date), "Regime": regime})
    return pd.DataFrame(rows)


def build_regime_diagnostics(validation_table, regimes):
    tagged = validation_table.merge(regimes, on="RebalanceDate", how="left")
    rows = []
    for regime in ("Risk-On", "Risk-Off", "Unavailable"):
        subset = tagged[tagged.Regime == regime]
        ic = build_rank_ic_table(subset); groups = build_group_return_table(subset)
        for horizon in [f"{h}D" for h in HORIZONS]:
            ic_values = _clean(ic[ic.Horizon == horizon].RankIC) if len(ic) else pd.Series(dtype=float)
            spreads = _clean(groups[(groups.Horizon == horizon) & (groups.Group == "Top")].LongShortSpread) if len(groups) else pd.Series(dtype=float)
            rows.append({"Regime": regime, "Horizon": horizon, "DateCount": subset.RebalanceDate.nunique(),
                         "ValidPairCount": int(ic[ic.Horizon == horizon].ValidPairs.sum()) if len(ic) else 0,
                         "MeanRankIC": float(ic_values.mean()) if len(ic_values) else None,
                         "MeanSpread": float(spreads.mean()) if len(spreads) else None})
    return pd.DataFrame(rows)


def build_coverage_diagnostics(validation_table):
    requested = validation_table.Ticker.nunique()
    rows = []
    for date in validation_table.RebalanceDate.drop_duplicates():
        frame = validation_table[validation_table.RebalanceDate == date]
        complete = frame.CompositeFactorScore.notna().sum()
        row = {"RebalanceDate": date, "RequestedSymbols": requested, "CompleteScores": int(complete),
               "ScoreCoverageRatio": complete/requested if requested else None}
        for horizon in HORIZONS: row[f"ValidForward{horizon}D"] = int(frame[f"ForwardReturn{horizon}D"].notna().sum())
        rows.append(row)
    return pd.DataFrame(rows)


def build_coverage_filter_comparison(validation, coverage):
    rules = (("No filter", 0), ("Coverage >= 80%", .8), ("Coverage >= 90%", .9), ("Coverage = 100%", 1))
    rows = []
    for name, threshold in rules:
        dates = coverage[coverage.ScoreCoverageRatio >= threshold].RebalanceDate
        subset = validation[validation.RebalanceDate.isin(dates)]
        ic, groups = build_rank_ic_table(subset), build_group_return_table(subset)
        for horizon in [f"{h}D" for h in HORIZONS]:
            iv = _clean(ic[ic.Horizon == horizon].RankIC) if len(ic) else pd.Series(dtype=float)
            sv = _clean(groups[(groups.Horizon == horizon)&(groups.Group == "Top")].LongShortSpread) if len(groups) else pd.Series(dtype=float)
            rows.append({"Filter": name, "Horizon": horizon, "DateCount": len(dates),
                         "MeanRankIC": float(iv.mean()) if len(iv) else None,
                         "MeanSpread": float(sv.mean()) if len(sv) else None})
    return pd.DataFrame(rows)


def build_robustness_summary(date_summary, robust_stats, influence, entry, regimes, coverage_comparison, benchmark_available):
    warnings = ["No transaction costs", "Current-Universe and survivorship bias", "High Trend/Momentum redundancy"]
    if not benchmark_available: warnings.append("SPY benchmark unavailable")
    if any(abs(value.get("BestThreeContribution") or 0) >= DATE_CONCENTRATION_THRESHOLD for value in date_summary.values()): warnings.append("Spread dominated by a small number of dates")
    if influence.SpreadChange.abs().max() >= SYMBOL_INFLUENCE_THRESHOLD: warnings.append("Large symbol influence")
    if ((entry.ICDifference.abs() >= ENTRY_IC_DIFFERENCE_THRESHOLD) | (entry.SpreadDifference.abs() >= ENTRY_SPREAD_DIFFERENCE_THRESHOLD)).any(): warnings.append("Same-close and next-close results differ materially")
    if any(abs(row.Mean-row.Median) >= MEAN_MEDIAN_DISAGREEMENT for _, row in robust_stats[robust_stats.Series == "Top-Bottom"].iterrows()): warnings.append("Mean and median materially disagree")
    return {"date_contributions": date_summary, "largest_symbol_influence": influence.loc[influence.SpreadChange.abs().idxmax()].to_dict(),
            "entry_comparison": entry.to_dict("records"), "regime_diagnostics": regimes.to_dict("records"),
            "coverage_comparison": coverage_comparison.to_dict("records"), "warnings": warnings}


def save_robustness_outputs(tables, output_paths=None):
    paths = dict(OUTPUT_PATHS if output_paths is None else output_paths)
    for name, table in tables.items():
        path = Path(paths[name]); path.parent.mkdir(parents=True, exist_ok=True); table.to_csv(path, index=False, encoding="utf-8"); paths[name] = path
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Factor validation robustness diagnostics")
    parser.add_argument("--validation", type=Path, default=RESULTS_DIR_PATH/"factor_validation.csv")
    parser.add_argument("--groups", type=Path, default=RESULTS_DIR_PATH/"factor_group_returns.csv")
    try:
        args = parser.parse_args(argv); validation = pd.read_csv(args.validation); groups = pd.read_csv(args.groups)
        symbols = load_active_universe(); market = {ticker: load_stock(ticker) for ticker in symbols}
        next_close = build_alternative_entry_validation(validation, market); entry = build_entry_comparison(validation, next_close)
        date_table = build_date_contribution_diagnostics(groups); robust = build_robust_return_statistics(groups); influence = build_symbol_influence_table(validation)
        spy_path = DATA_DIR_PATH/"SPY.csv"; spy = load_stock("SPY") if spy_path.is_file() else None
        regimes = classify_market_regimes(validation.RebalanceDate.drop_duplicates().tolist(), spy)
        regime_results = build_regime_diagnostics(validation, regimes); coverage = build_coverage_diagnostics(validation); coverage_results = build_coverage_filter_comparison(validation, coverage)
        tables = {"date_contributions":date_table,"robust_stats":robust,"symbol_influence":influence,"entry_comparison":entry,"regimes":regime_results,"coverage":coverage}
        paths = save_robustness_outputs(tables); summary = build_robustness_summary(summarize_date_contributions(date_table),robust,influence,entry,regime_results,coverage_results,spy is not None)
        print("Factor Validation Robustness Diagnostics")
        print(f"Dates: {validation.RebalanceDate.nunique()}"); print("Warnings:")
        for warning in summary["warnings"]: print(f"- {warning}")
        print("Outputs:"); [print(display_path(path)) for path in paths.values()]
        return 0
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        print(f"Robustness diagnostics error: {error}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
