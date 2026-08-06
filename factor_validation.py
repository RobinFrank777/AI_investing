"""Leakage-controlled historical validation of the composite factor baseline."""

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from config import RESULTS_DIR_PATH, display_path
from factor_composite import build_composite_factor_table
from factor_normalization import build_normalized_factor_table
from price_factors import calculate_price_factors
from stock_loader import load_stock
from universe_source import load_active_universe


HORIZONS = (5, 10, 20, 60)
MIN_FACTOR_HISTORY = 60
MIN_IC_PAIRS = 3
GROUP_FRACTION = 0.20
SMALL_CROSS_SECTION = 10
LOW_COVERAGE_RATIO = 0.50
HIGH_REDUNDANCY_CORRELATION = 0.80

VALIDATION_COLUMNS = [
    "RebalanceDate", "Ticker", "CompositeFactorScore", "CompositeRank",
    "CompositePercentile", "TrendValue", "MomentumValue", "Volatility20D",
    "TrendPercentile", "MomentumPercentile", "LowVolatilityPercentile",
    "ForwardReturn5D", "ForwardReturn10D", "ForwardReturn20D",
    "ForwardReturn60D", "ValidationStatus", "ValidationMissingFields",
    "ValidationMessage",
]
IC_COLUMNS = ["RebalanceDate", "Horizon", "ValidPairs", "RankIC"]
GROUP_COLUMNS = [
    "RebalanceDate", "Horizon", "Group", "SelectedCount",
    "ValidReturnCount", "AverageForwardReturn", "LongShortSpread",
]
TURNOVER_COLUMNS = [
    "PreviousDate", "CurrentDate", "PreviousTopCount", "CurrentTopCount",
    "RetainedCount", "Turnover",
]
OUTPUT_PATHS = {
    "validation": RESULTS_DIR_PATH / "factor_validation.csv",
    "rank_ic": RESULTS_DIR_PATH / "factor_rank_ic.csv",
    "group_returns": RESULTS_DIR_PATH / "factor_group_returns.csv",
    "turnover": RESULTS_DIR_PATH / "factor_turnover.csv",
}


def _market_frame(data):
    if not isinstance(data, pd.DataFrame) or "Date" not in data or "Close" not in data:
        raise ValueError("market data requires Date and Close columns")
    frame = data.copy(deep=True)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame.dropna(subset=["Date", "Close"])
    finite = frame["Close"].map(lambda value: math.isfinite(value))
    return frame[finite].sort_values("Date", kind="mergesort").reset_index(drop=True)


def build_rebalance_dates(
    market_data, start_date=None, end_date=None, rebalance_frequency="monthly"
):
    """Return month-end last available dates after at least 60 history rows exist."""
    if rebalance_frequency != "monthly":
        raise ValueError("only monthly rebalance frequency is supported")
    frames = []
    for data in market_data.values():
        try:
            frame = _market_frame(data)
        except ValueError:
            continue
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return []
    dates = pd.Series(sorted(set().union(*(set(frame["Date"]) for frame in frames))))
    if start_date is not None:
        start = pd.to_datetime(start_date, errors="raise")
        dates = dates[dates >= start]
    if end_date is not None:
        end = pd.to_datetime(end_date, errors="raise")
        dates = dates[dates <= end]
    monthly = dates.groupby(dates.dt.to_period("M")).max().tolist()
    return [
        date for date in monthly
        if any((frame["Date"] <= date).sum() >= MIN_FACTOR_HISTORY for frame in frames)
    ]


def build_historical_factor_cross_section(market_data, rebalance_date, symbols=None):
    """Build native factors using only observations on or before the cutoff."""
    cutoff = pd.to_datetime(rebalance_date, errors="raise")
    requested = list(market_data) if symbols is None else list(symbols)
    rows = []
    for ticker in requested:
        try:
            frame = _market_frame(market_data[ticker])
            truncated = frame[frame["Date"] <= cutoff].copy()
            factors = calculate_price_factors(truncated)
        except (KeyError, ValueError, TypeError):
            factors = {name: None for name in ("TrendValue", "MomentumValue", "Volatility20D")}
        rows.append({
            "Ticker": ticker, "AsOfDate": cutoff.strftime("%Y-%m-%d"),
            "FactorStatus": "PASS" if all(value is not None for value in factors.values()) else "PARTIAL",
            **factors,
        })
    raw = pd.DataFrame(rows)
    normalized = build_normalized_factor_table(raw)
    return build_composite_factor_table(normalized)


def calculate_forward_return(data, rebalance_date, horizon):
    """Return close[t+N] / close[t] - 1 using an actual rebalance-date close."""
    if not isinstance(horizon, int) or horizon <= 0:
        raise ValueError("horizon must be a positive integer")
    frame = _market_frame(data)
    cutoff = pd.to_datetime(rebalance_date, errors="raise")
    matches = frame.index[frame["Date"] == cutoff].tolist()
    if not matches:
        return None
    entry_index = matches[-1]
    exit_index = entry_index + horizon
    if exit_index >= len(frame):
        return None
    entry = frame.at[entry_index, "Close"]
    if entry == 0:
        return None
    result = float(frame.at[exit_index, "Close"] / entry - 1)
    return result if math.isfinite(result) else None


def build_factor_validation_table(
    symbols=None, market_data=None, start_date=None, end_date=None,
    rebalance_frequency="monthly"
):
    """Build deterministic ticker/date observations from raw market data only."""
    requested = load_active_universe() if symbols is None else list(symbols)
    histories = {}
    if market_data is None:
        for ticker in requested:
            try:
                histories[ticker] = load_stock(ticker)
            except Exception:
                histories[ticker] = pd.DataFrame()
    else:
        histories = market_data
    dates = build_rebalance_dates(histories, start_date, end_date, rebalance_frequency)
    rows = []
    for date in dates:
        cross = build_historical_factor_cross_section(histories, date, requested)
        indexed = cross.set_index("Ticker", drop=False)
        for ticker in requested:
            current = indexed.loc[ticker]
            if isinstance(current, pd.DataFrame):
                current = current.iloc[0]
            missing = []
            result = {
                "RebalanceDate": date.strftime("%Y-%m-%d"), "Ticker": ticker,
                **{name: current.get(name) for name in (
                    "CompositeFactorScore", "CompositeRank", "CompositePercentile",
                    "TrendPercentile", "MomentumPercentile", "LowVolatilityPercentile",
                )},
            }
            try:
                truncated = _market_frame(histories[ticker])
                truncated = truncated[truncated["Date"] <= date]
                native = calculate_price_factors(truncated)
            except Exception:
                native = {name: None for name in ("TrendValue", "MomentumValue", "Volatility20D")}
            result.update(native)
            for horizon in HORIZONS:
                field = f"ForwardReturn{horizon}D"
                try:
                    result[field] = calculate_forward_return(histories[ticker], date, horizon)
                except Exception:
                    result[field] = None
                if result[field] is None:
                    missing.append(field)
            if _finite_or_none(result["CompositeFactorScore"]) is None:
                missing.insert(0, "CompositeFactorScore")
            result["ValidationMissingFields"] = ";".join(missing)
            result["ValidationStatus"] = "PASS" if not missing else "PARTIAL"
            result["ValidationMessage"] = "Same-close entry assumption"
            rows.append(result)
    return pd.DataFrame(rows, columns=VALIDATION_COLUMNS)


def _finite_or_none(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _spearman(first, second):
    pair = pd.DataFrame({"a": first, "b": second}).apply(pd.to_numeric, errors="coerce").dropna()
    if len(pair) < MIN_IC_PAIRS or pair.a.nunique() < 2 or pair.b.nunique() < 2:
        return len(pair), None
    value = pair.a.rank(method="average").corr(pair.b.rank(method="average"))
    return len(pair), float(value) if pd.notna(value) and math.isfinite(value) else None


def build_rank_ic_table(validation_table):
    rows = []
    dates = validation_table["RebalanceDate"].drop_duplicates().tolist()
    for date in dates:
        group = validation_table[validation_table["RebalanceDate"] == date]
        for horizon in HORIZONS:
            count, ic = _spearman(group["CompositeFactorScore"], group[f"ForwardReturn{horizon}D"])
            rows.append({"RebalanceDate": date, "Horizon": f"{horizon}D", "ValidPairs": count, "RankIC": ic})
    return pd.DataFrame(rows, columns=IC_COLUMNS)


def build_group_return_table(validation_table):
    """Use stable top/bottom ceil(20%) groups and an equal-weight middle."""
    rows = []
    for date in validation_table["RebalanceDate"].drop_duplicates():
        date_rows = validation_table[validation_table.RebalanceDate == date].copy()
        date_rows["_order"] = range(len(date_rows))
        valid = date_rows.dropna(subset=["CompositeFactorScore"]).sort_values(
            ["CompositeFactorScore", "_order"], ascending=[False, True], kind="mergesort"
        )
        size = max(1, math.ceil(len(valid) * GROUP_FRACTION)) if len(valid) else 0
        groups = {
            "Top": valid.head(size),
            "Middle": valid.iloc[size:len(valid)-size] if len(valid) > size * 2 else valid.iloc[0:0],
            "Bottom": valid.tail(size),
        }
        for horizon in HORIZONS:
            returns = {}
            for name, selected in groups.items():
                values = pd.to_numeric(selected[f"ForwardReturn{horizon}D"], errors="coerce").dropna()
                returns[name] = float(values.mean()) if len(values) else None
            spread = None if returns["Top"] is None or returns["Bottom"] is None else returns["Top"] - returns["Bottom"]
            for name, selected in groups.items():
                valid_count = pd.to_numeric(selected[f"ForwardReturn{horizon}D"], errors="coerce").notna().sum()
                rows.append({
                    "RebalanceDate": date, "Horizon": f"{horizon}D", "Group": name,
                    "SelectedCount": len(selected), "ValidReturnCount": int(valid_count),
                    "AverageForwardReturn": returns[name], "LongShortSpread": spread,
                })
    return pd.DataFrame(rows, columns=GROUP_COLUMNS)


def build_turnover_table(validation_table):
    dates = validation_table["RebalanceDate"].drop_duplicates().tolist()
    rows = []
    previous_date = None
    previous_top = set()
    for date in dates:
        current = validation_table[validation_table.RebalanceDate == date].copy()
        current["_order"] = range(len(current))
        valid = current.dropna(subset=["CompositeFactorScore"]).sort_values(
            ["CompositeFactorScore", "_order"], ascending=[False, True], kind="mergesort"
        )
        size = max(1, math.ceil(len(valid) * GROUP_FRACTION)) if len(valid) else 0
        current_top = set(valid.head(size).Ticker)
        retained = len(previous_top & current_top) if previous_date is not None else 0
        turnover = None if previous_date is None or not previous_top else 1 - retained / len(previous_top)
        rows.append({
            "PreviousDate": previous_date, "CurrentDate": date,
            "PreviousTopCount": len(previous_top), "CurrentTopCount": len(current_top),
            "RetainedCount": retained, "Turnover": turnover,
        })
        previous_date, previous_top = date, current_top
    return pd.DataFrame(rows, columns=TURNOVER_COLUMNS)


def _series_summary(values):
    clean = pd.to_numeric(values, errors="coerce").dropna()
    std = clean.std(ddof=1) if len(clean) >= 2 else None
    mean = clean.mean() if len(clean) else None
    return {
        "count": int(len(clean)), "mean": float(mean) if mean is not None else None,
        "median": float(clean.median()) if len(clean) else None,
        "std": float(std) if std is not None and pd.notna(std) else None,
        "positive_ratio": float((clean > 0).mean()) if len(clean) else None,
        "information_ratio": (
            float(mean / std) if std is not None and pd.notna(std) and std != 0 else None
        ),
    }


def build_validation_summary(validation, rank_ic, groups, turnover, symbol_count=None):
    dates = validation.RebalanceDate.drop_duplicates().tolist()
    warnings = ["Same-close entry assumption", "Current-Universe and survivorship bias"]
    coverage_by_date = {
        date: int(validation[validation.RebalanceDate == date].CompositeFactorScore.notna().sum())
        for date in dates
    }
    if coverage_by_date and min(coverage_by_date.values()) < SMALL_CROSS_SECTION:
        warnings.append("Small cross-sectional sample")
    if coverage_by_date and len(set(coverage_by_date.values())) > 1:
        warnings.append("Mixed symbol date coverage")
    coverage_by_horizon = {
        f"{h}D": int(validation[f"ForwardReturn{h}D"].notna().sum()) for h in HORIZONS
    }
    if any(count < len(validation) for count in coverage_by_horizon.values()):
        warnings.append("Insufficient forward observations")
    pair = validation[["TrendPercentile", "MomentumPercentile"]].apply(
        pd.to_numeric, errors="coerce"
    ).dropna()
    if len(pair) >= 2:
        redundancy = pair.TrendPercentile.corr(pair.MomentumPercentile)
        if pd.notna(redundancy) and abs(redundancy) >= HIGH_REDUNDANCY_CORRELATION:
            warnings.append("High Trend/Momentum redundancy")
    ic_summary = {
        f"{h}D": _series_summary(rank_ic[rank_ic.Horizon == f"{h}D"].RankIC)
        for h in HORIZONS
    }
    group_summary = {}
    spread_summary = {}
    for h in HORIZONS:
        subset = groups[groups.Horizon == f"{h}D"]
        group_summary[f"{h}D"] = {
            name: _series_summary(subset[subset.Group == name].AverageForwardReturn)
            for name in ("Top", "Middle", "Bottom")
        }
        spreads = subset[subset.Group == "Top"].LongShortSpread
        spread_summary[f"{h}D"] = _series_summary(spreads)
    turnover_values = pd.to_numeric(turnover.Turnover, errors="coerce").dropna()
    return {
        "symbol_count": int(symbol_count if symbol_count is not None else validation.Ticker.nunique()),
        "rebalance_count": len(dates), "observation_count": len(validation),
        "date_range": [dates[0], dates[-1]] if dates else [], "horizons": [f"{h}D" for h in HORIZONS],
        "coverage_by_date": coverage_by_date, "coverage_by_horizon": coverage_by_horizon,
        "ic_summary": ic_summary, "group_return_summary": group_summary,
        "long_short_summary": spread_summary,
        "turnover_summary": {
            "count": len(turnover_values),
            "mean": float(turnover_values.mean()) if len(turnover_values) else None,
        }, "warnings": warnings,
    }


def save_factor_validation(validation, output_paths=None):
    paths = dict(OUTPUT_PATHS if output_paths is None else output_paths)
    tables = {
        "validation": validation, "rank_ic": build_rank_ic_table(validation),
        "group_returns": build_group_return_table(validation),
        "turnover": build_turnover_table(validation),
    }
    for name, table in tables.items():
        path = Path(paths[name]); path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False, encoding="utf-8"); paths[name] = path
    return paths


def _parser():
    parser = argparse.ArgumentParser(description="Validate Composite Factor forward returns")
    parser.add_argument("--start"); parser.add_argument("--end")
    parser.add_argument("--frequency", default="monthly")
    parser.add_argument("--limit-symbols", type=int)
    return parser


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
        if args.limit_symbols is not None and args.limit_symbols <= 0:
            raise ValueError("limit-symbols must be positive")
        symbols = load_active_universe()
        if args.limit_symbols is not None:
            symbols = symbols[:args.limit_symbols]
        validation = build_factor_validation_table(
            symbols, start_date=args.start, end_date=args.end,
            rebalance_frequency=args.frequency,
        )
        ic = build_rank_ic_table(validation); groups = build_group_return_table(validation)
        turnover = build_turnover_table(validation)
        summary = build_validation_summary(validation, ic, groups, turnover, len(symbols))
        paths = save_factor_validation(validation)
        print("Composite Factor Forward Validation")
        print(f"Symbols Requested: {len(symbols)}")
        print(f"Rebalance Dates: {summary['rebalance_count']}")
        print(f"Observations: {summary['observation_count']}")
        print("Date Range: " + " to ".join(summary["date_range"]))
        print("\nRank IC")
        for horizon in summary["horizons"]:
            print(f"{horizon}: {summary['ic_summary'][horizon]['mean']}")
        print("\nOutputs:")
        for path in paths.values(): print(display_path(path))
        return 0
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        print(f"Factor validation error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
