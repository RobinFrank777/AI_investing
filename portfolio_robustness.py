"""Diagnostic robustness scenarios for the Phase 5B-2 research portfolio."""

from pathlib import Path

import pandas as pd

from config import ACCOUNT_VALUE
from portfolio_backtest import (
    calculate_portfolio_metrics,
    load_trade_events,
    simulate_portfolio,
)
from stock_loader import load_stock


PROJECT_ROOT = Path(__file__).resolve().parent
BENCHMARK_OUTPUT_PATH = PROJECT_ROOT / "results" / "portfolio_benchmark_comparison.csv"
EXECUTION_OUTPUT_PATH = PROJECT_ROOT / "results" / "execution_price_sensitivity.csv"
COST_OUTPUT_PATH = PROJECT_ROOT / "results" / "transaction_cost_sensitivity.csv"
CONTRIBUTION_OUTPUT_PATH = PROJECT_ROOT / "results" / "ticker_performance_contribution.csv"
COST_SCENARIOS = (0, 10, 25, 50)


def build_benchmark_comparison(equity, benchmark_data=None):
    curve = equity.copy()
    curve["Date"] = pd.to_datetime(curve["Date"], errors="raise")
    result = curve.loc[:, ["Date", "PortfolioValue"]].rename(
        columns={"PortfolioValue": "AI_Portfolio_Value"}
    )
    sources = {}
    for ticker in ("SPY", "QQQ"):
        source = (
            load_stock(ticker)
            if benchmark_data is None
            else benchmark_data[ticker].copy(deep=True)
        )
        source["Date"] = pd.to_datetime(source["Date"], errors="raise")
        sources[ticker] = source.set_index("Date")["Close"]
    common_end = min(result["Date"].max(), *(series.index.max() for series in sources.values()))
    result = result.loc[result["Date"] <= common_end].reset_index(drop=True)
    for ticker in ("SPY", "QQQ"):
        close = sources[ticker]
        aligned = result["Date"].map(close)
        if aligned.isna().any():
            missing = result.loc[aligned.isna(), "Date"].dt.strftime("%Y-%m-%d")
            raise ValueError(f"{ticker} missing benchmark dates: {', '.join(missing)}")
        result[f"{ticker}_Value"] = aligned / aligned.iloc[0] * ACCOUNT_VALUE
    result["AI_Cumulative_Return"] = (
        result["AI_Portfolio_Value"] / result["AI_Portfolio_Value"].iloc[0] - 1
    )
    result["SPY_Cumulative_Return"] = result["SPY_Value"] / ACCOUNT_VALUE - 1
    result["QQQ_Cumulative_Return"] = result["QQQ_Value"] / ACCOUNT_VALUE - 1
    return result


def build_next_open_events(events, market_data=None, holding_days=20):
    adjusted = []
    for _, event in events.iterrows():
        ticker = event["Ticker"]
        market = (
            load_stock(ticker)
            if market_data is None
            else market_data[ticker].copy(deep=True)
        )
        market["Date"] = pd.to_datetime(market["Date"], errors="raise")
        market = market.sort_values("Date", kind="mergesort").reset_index(drop=True)
        signal_date = pd.to_datetime(event["EntryDate"], errors="raise")
        matches = market.index[market["Date"] == signal_date]
        if len(matches) != 1:
            raise ValueError(f"signal date missing or duplicated for {ticker}")
        entry_index = int(matches[0]) + 1
        exit_index = entry_index + holding_days
        changed = event.copy()
        if exit_index >= len(market):
            changed["EntryDate"] = pd.NaT
            changed[f"ExitDate_{holding_days}D"] = pd.NaT
        else:
            changed["EntryDate"] = market.at[entry_index, "Date"]
            changed["EntryPrice"] = market.at[entry_index, "Open"]
            changed[f"ExitDate_{holding_days}D"] = market.at[exit_index, "Date"]
        adjusted.append(changed)
    return pd.DataFrame(adjusted).dropna(subset=["EntryDate"])


def _scenario_metrics(name, events, market_data=None, transaction_cost_bps=0):
    trades, equity = simulate_portfolio(
        events,
        market_data=market_data,
        transaction_cost_bps=transaction_cost_bps,
    )
    metrics = calculate_portfolio_metrics(trades, equity).iloc[0]
    return {
        "Scenario": name,
        "TotalReturn": metrics["TotalReturn"],
        "AnnualizedReturn": metrics["AnnualizedReturn"],
        "MaximumDrawdown": metrics["MaximumDrawdown"],
        "SharpeEstimate": metrics["SharpeEstimate"],
        "WinRate": metrics["WinRate"],
        "TotalTrades": metrics["TotalTrades"],
    }


def analyze_execution_sensitivity(events, market_data=None):
    next_open = build_next_open_events(events, market_data=market_data)
    rows = [
        _scenario_metrics("Signal Close", events, market_data=market_data),
        _scenario_metrics("Next Trading Day Open", next_open, market_data=market_data),
    ]
    return pd.DataFrame(rows)


def analyze_cost_sensitivity(events, market_data=None, scenarios=COST_SCENARIOS):
    rows = []
    for bps in scenarios:
        metrics = _scenario_metrics(
            f"{bps} bps per side",
            events,
            market_data=market_data,
            transaction_cost_bps=bps,
        )
        rows.append(
            {
                "TransactionCostBpsPerSide": bps,
                "TotalReturn": metrics["TotalReturn"],
                "AnnualizedReturn": metrics["AnnualizedReturn"],
                "SharpeEstimate": metrics["SharpeEstimate"],
                "MaximumDrawdown": metrics["MaximumDrawdown"],
            }
        )
    return pd.DataFrame(rows)


def calculate_ticker_contribution(trade_log):
    rows = []
    total_profit = trade_log["ProfitLoss"].sum()
    for ticker, trades in trade_log.groupby("Ticker", sort=True):
        profit = trades["ProfitLoss"].sum()
        rows.append(
            {
                "Ticker": ticker,
                "TradeCount": len(trades),
                "WinRate": (trades["ProfitLoss"] > 0).mean(),
                "TotalProfitLoss": profit,
                "AverageReturn": trades["Return"].mean(),
                "LargestGain": trades["ProfitLoss"].max(),
                "LargestLoss": trades["ProfitLoss"].min(),
                "ContributionPercent": (
                    profit / total_profit if total_profit != 0 else float("nan")
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "TotalProfitLoss", ascending=False, kind="mergesort"
    ).reset_index(drop=True)


def _save(table, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)


def run_robustness_analysis():
    events = load_trade_events()
    baseline_trades, baseline_equity = simulate_portfolio(events)
    benchmark = build_benchmark_comparison(baseline_equity)
    execution = analyze_execution_sensitivity(events)
    costs = analyze_cost_sensitivity(events)
    contribution = calculate_ticker_contribution(baseline_trades)
    _save(benchmark, BENCHMARK_OUTPUT_PATH)
    _save(execution, EXECUTION_OUTPUT_PATH)
    _save(costs, COST_OUTPUT_PATH)
    _save(contribution, CONTRIBUTION_OUTPUT_PATH)
    return benchmark, execution, costs, contribution


if __name__ == "__main__":
    benchmark, execution, costs, contribution = run_robustness_analysis()
    print(execution.to_string(index=False))
    print(costs.to_string(index=False))
    print(contribution.to_string(index=False))
