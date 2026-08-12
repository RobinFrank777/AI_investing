"""Capital-constrained research simulation over production trade events."""

from pathlib import Path

import numpy as np
import pandas as pd

from config import ACCOUNT_VALUE, MAX_HOLDINGS
from stock_loader import load_stock


PROJECT_ROOT = Path(__file__).resolve().parent
EVENTS_INPUT_PATH = PROJECT_ROOT / "results" / "production_trade_events.csv"
TRADE_LOG_OUTPUT_PATH = PROJECT_ROOT / "results" / "portfolio_trade_log.csv"
EQUITY_OUTPUT_PATH = PROJECT_ROOT / "results" / "portfolio_equity_curve.csv"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "results" / "portfolio_backtest_summary.csv"
TRADE_COLUMNS = (
    "Ticker", "EntryDate", "EntryPrice", "ExitDate", "ExitPrice", "Shares",
    "PositionValue", "HoldingDays", "Return", "ProfitLoss", "ExitReason",
)
EQUITY_COLUMNS = (
    "Date", "PortfolioValue", "Cash", "Positions", "PositionsValue",
    "DailyReturn", "Drawdown",
)
SUMMARY_COLUMNS = (
    "StartingCapital", "EndingPortfolioValue", "TotalReturn",
    "AnnualizedReturn", "MaximumDrawdown", "AnnualizedVolatility",
    "SharpeEstimate", "TotalTrades", "WinningTrades", "LosingTrades",
    "WinRate", "AverageGain", "AverageLoss", "ProfitFactor",
    "AveragePositions", "MaximumConcurrentPositions",
    "AverageInvestedPercentage", "HoldingDays", "MaximumPositions",
)


def load_trade_events(path=EVENTS_INPUT_PATH):
    events = pd.read_csv(path)
    required = {
        "Ticker", "EntryDate", "EntryPrice", "EntryFinalScore",
        "ExitDate_20D", "ExitDate_60D",
    }
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError("trade events missing required columns: " + ", ".join(missing))
    return events


def _prepare_market(ticker, market_data=None):
    source = load_stock(ticker) if market_data is None else market_data[ticker].copy(deep=True)
    source["Date"] = pd.to_datetime(source["Date"], errors="raise")
    source = source.sort_values("Date", kind="mergesort").reset_index(drop=True)
    if source["Date"].duplicated().any():
        raise ValueError(f"duplicate market date for {ticker}")
    return source


def _market_maps(tickers, market_data=None):
    maps = {}
    calendars = []
    for ticker in sorted(set(tickers)):
        market = _prepare_market(ticker, market_data)
        maps[ticker] = pd.Series(market["Close"].values, index=market["Date"]).to_dict()
        calendars.append(market["Date"])
    calendar = pd.DatetimeIndex(pd.concat(calendars).drop_duplicates().sort_values())
    return maps, calendar


def simulate_portfolio(
    events,
    market_data=None,
    *,
    starting_capital=ACCOUNT_VALUE,
    max_positions=MAX_HOLDINGS,
    holding_days=20,
    transaction_cost_bps=0,
):
    """Execute fixed-horizon, equal-slot positions with exits before entries."""
    if holding_days not in (20, 60):
        raise ValueError("holding_days must be 20 or 60")
    if starting_capital <= 0 or max_positions <= 0 or transaction_cost_bps < 0:
        raise ValueError("capital and maximum positions must be positive")
    cost_rate = transaction_cost_bps / 10_000
    events = events.copy()
    events["EntryDate"] = pd.to_datetime(events["EntryDate"], errors="raise")
    exit_column = f"ExitDate_{holding_days}D"
    events[exit_column] = pd.to_datetime(events[exit_column], errors="coerce")
    events = events.dropna(subset=[exit_column]).sort_values(
        ["EntryDate", "EntryFinalScore", "Ticker"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    if events.empty:
        return (
            pd.DataFrame(columns=TRADE_COLUMNS),
            pd.DataFrame(columns=EQUITY_COLUMNS),
        )
    prices, full_calendar = _market_maps(events["Ticker"], market_data)
    start_date = events["EntryDate"].min()
    end_date = events[exit_column].max()
    calendar = full_calendar[(full_calendar >= start_date) & (full_calendar <= end_date)]
    cash = float(starting_capital)
    active = {}
    trades = []
    equity_rows = []
    previous_value = float(starting_capital)

    for date in calendar:
        exiting = [ticker for ticker, position in active.items() if position["ExitDate"] == date]
        for ticker in sorted(exiting):
            position = active.pop(ticker)
            if date not in prices[ticker]:
                raise ValueError(f"missing exit price for {ticker} on {date.date()}")
            exit_price = float(prices[ticker][date])
            gross_proceeds = position["Shares"] * exit_price
            exit_cost = gross_proceeds * cost_rate
            net_proceeds = gross_proceeds - exit_cost
            cash += net_proceeds
            profit_loss = (
                net_proceeds - position["PositionValue"] - position["EntryCost"]
            )
            trades.append(
                {
                    "Ticker": ticker,
                    "EntryDate": position["EntryDate"],
                    "EntryPrice": position["EntryPrice"],
                    "ExitDate": date,
                    "ExitPrice": exit_price,
                    "Shares": position["Shares"],
                    "PositionValue": position["PositionValue"],
                    "HoldingDays": holding_days,
                    "Return": profit_loss / (
                        position["PositionValue"] + position["EntryCost"]
                    ),
                    "ProfitLoss": profit_loss,
                    "ExitReason": f"TIME_EXIT_{holding_days}D",
                }
            )

        todays_entries = events.loc[events["EntryDate"] == date]
        for _, event in todays_entries.iterrows():
            ticker = event["Ticker"]
            if ticker in active or len(active) >= max_positions:
                continue
            remaining_slots = max_positions - len(active)
            allocation = cash / remaining_slots
            entry_price = float(event["EntryPrice"])
            shares = int(allocation // (entry_price * (1 + cost_rate)))
            if shares <= 0:
                continue
            position_value = shares * entry_price
            entry_cost = position_value * cost_rate
            cash -= position_value + entry_cost
            active[ticker] = {
                "EntryDate": date,
                "EntryPrice": entry_price,
                "ExitDate": event[exit_column],
                "Shares": shares,
                "PositionValue": position_value,
                "EntryCost": entry_cost,
            }

        positions_value = 0.0
        for ticker, position in active.items():
            if date not in prices[ticker]:
                raise ValueError(f"missing mark price for {ticker} on {date.date()}")
            positions_value += position["Shares"] * float(prices[ticker][date])
        portfolio_value = cash + positions_value
        daily_return = portfolio_value / previous_value - 1 if equity_rows else 0.0
        equity_rows.append(
            {
                "Date": date,
                "PortfolioValue": portfolio_value,
                "Cash": cash,
                "Positions": len(active),
                "PositionsValue": positions_value,
                "DailyReturn": daily_return,
            }
        )
        previous_value = portfolio_value

    trade_log = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    equity = pd.DataFrame(equity_rows)
    equity["Drawdown"] = equity["PortfolioValue"] / equity["PortfolioValue"].cummax() - 1
    equity = equity.loc[:, EQUITY_COLUMNS]
    for column in ("EntryDate", "ExitDate"):
        if column in trade_log:
            trade_log[column] = pd.to_datetime(trade_log[column]).dt.strftime("%Y-%m-%d")
    equity["Date"] = pd.to_datetime(equity["Date"]).dt.strftime("%Y-%m-%d")
    return trade_log, equity


def calculate_portfolio_metrics(
    trade_log,
    equity,
    *,
    starting_capital=ACCOUNT_VALUE,
    holding_days=20,
    max_positions=MAX_HOLDINGS,
):
    if equity.empty:
        ending_value = float(starting_capital)
        periods = 0
        daily_returns = pd.Series(dtype=float)
        max_drawdown = 0.0
    else:
        ending_value = float(equity.iloc[-1]["PortfolioValue"])
        periods = max(len(equity) - 1, 0)
        daily_returns = equity["DailyReturn"].iloc[1:]
        max_drawdown = float(equity["Drawdown"].min())
    total_return = ending_value / starting_capital - 1
    annualized_return = (
        (ending_value / starting_capital) ** (252 / periods) - 1
        if periods > 0 and ending_value > 0
        else float("nan")
    )
    volatility = daily_returns.std(ddof=1) * np.sqrt(252)
    sharpe = (
        daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(252)
        if len(daily_returns) > 1 and daily_returns.std(ddof=1) != 0
        else float("nan")
    )
    gains = trade_log.loc[trade_log["ProfitLoss"] > 0, "ProfitLoss"]
    losses = trade_log.loc[trade_log["ProfitLoss"] < 0, "ProfitLoss"]
    profit_factor = gains.sum() / abs(losses.sum()) if not losses.empty else float("nan")
    invested_percentage = (
        equity["PositionsValue"] / equity["PortfolioValue"] if not equity.empty else pd.Series(dtype=float)
    )
    return pd.DataFrame(
        [
            {
                "StartingCapital": starting_capital,
                "EndingPortfolioValue": ending_value,
                "TotalReturn": total_return,
                "AnnualizedReturn": annualized_return,
                "MaximumDrawdown": max_drawdown,
                "AnnualizedVolatility": volatility,
                "SharpeEstimate": sharpe,
                "TotalTrades": len(trade_log),
                "WinningTrades": len(gains),
                "LosingTrades": len(losses),
                "WinRate": (trade_log["ProfitLoss"] > 0).mean(),
                "AverageGain": gains.mean(),
                "AverageLoss": losses.mean(),
                "ProfitFactor": profit_factor,
                "AveragePositions": equity["Positions"].mean() if not equity.empty else 0.0,
                "MaximumConcurrentPositions": equity["Positions"].max() if not equity.empty else 0,
                "AverageInvestedPercentage": invested_percentage.mean() if not equity.empty else 0.0,
                "HoldingDays": holding_days,
                "MaximumPositions": max_positions,
            }
        ],
        columns=SUMMARY_COLUMNS,
    )


def run_portfolio_backtest(
    events_input_path=EVENTS_INPUT_PATH,
    trade_log_output_path=TRADE_LOG_OUTPUT_PATH,
    equity_output_path=EQUITY_OUTPUT_PATH,
    summary_output_path=SUMMARY_OUTPUT_PATH,
    *,
    holding_days=20,
):
    events = load_trade_events(events_input_path)
    trades, equity = simulate_portfolio(events, holding_days=holding_days)
    summary = calculate_portfolio_metrics(trades, equity, holding_days=holding_days)
    for path in (trade_log_output_path, equity_output_path, summary_output_path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(trade_log_output_path, index=False)
    equity.to_csv(equity_output_path, index=False)
    summary.to_csv(summary_output_path, index=False)
    return trades, equity, summary


if __name__ == "__main__":
    trades, equity, summary = run_portfolio_backtest()
    print(summary.to_string(index=False))
    print(f"Trades: {TRADE_LOG_OUTPUT_PATH} ({len(trades)} rows)")
    print(f"Equity: {EQUITY_OUTPUT_PATH} ({len(equity)} rows)")
