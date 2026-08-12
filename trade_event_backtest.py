"""Convert production-faithful BUY observations into entry trade events."""

from pathlib import Path

import pandas as pd

from stock_loader import load_stock


PROJECT_ROOT = Path(__file__).resolve().parent
SIGNALS_INPUT_PATH = PROJECT_ROOT / "results" / "production_backtest_signals.csv"
EVENTS_OUTPUT_PATH = PROJECT_ROOT / "results" / "production_trade_events.csv"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "results" / "production_trade_event_summary.csv"
EVENT_COLUMNS = (
    "Ticker", "EntryDate", "EntryPrice", "EntryFinalScore", "EntryTrendScore",
    "EntryMomentumScore", "EntryRSScore", "EntryNearHighScore",
    "EntryVolumeScore", "EntryRiskScore", "ExitDate_5D", "ExitDate_20D",
    "ExitDate_60D", "Return_5D", "Return_20D", "Return_60D",
    "MaximumFavorableExcursion", "MaximumAdverseExcursion",
)
SUMMARY_COLUMNS = (
    "TotalEntries", "SymbolsCount", "AverageEntryScore",
    "AverageReturn_5D", "MedianReturn_5D", "WinRate_5D", "StdDevReturn_5D",
    "AverageReturn_20D", "MedianReturn_20D", "WinRate_20D", "StdDevReturn_20D",
    "AverageReturn_60D", "MedianReturn_60D", "WinRate_60D", "StdDevReturn_60D",
    "MaximumDrawdownProxy", "AverageAdverseExcursion",
    "AverageFavorableExcursion",
)
REQUIRED_SIGNAL_COLUMNS = (
    "Ticker", "SignalDate", "FinalScore", "TrendScore", "MomentumScore",
    "RSScore", "NearHighScore", "VolumeScore", "RiskScore", "TradeSignal",
)


def load_signal_history(path=SIGNALS_INPUT_PATH):
    signals = pd.read_csv(path)
    missing = [column for column in REQUIRED_SIGNAL_COLUMNS if column not in signals]
    if missing:
        raise ValueError("signal history missing required columns: " + ", ".join(missing))
    signals = signals.copy()
    signals["SignalDate"] = pd.to_datetime(signals["SignalDate"], errors="raise")
    return signals.sort_values(["Ticker", "SignalDate"], kind="mergesort")


def _prepare_market(ticker, market_data=None):
    source = load_stock(ticker) if market_data is None else market_data[ticker].copy(deep=True)
    source["Date"] = pd.to_datetime(source["Date"], errors="raise")
    return source.sort_values("Date", kind="mergesort").reset_index(drop=True)


def identify_entry_signals(signals, market_data=None):
    """Return BUY rows whose immediately prior trading-row state was not BUY."""
    entries = []
    for ticker, ticker_signals in signals.groupby("Ticker", sort=False):
        market = _prepare_market(ticker, market_data)
        positions = pd.Series(market.index, index=market["Date"]).to_dict()
        buy_positions = {
            positions[date]
            for date in ticker_signals.loc[
                ticker_signals["TradeSignal"] == "BUY", "SignalDate"
            ]
            if date in positions
        }
        for _, row in ticker_signals.loc[
            ticker_signals["TradeSignal"] == "BUY"
        ].iterrows():
            if row["SignalDate"] not in positions:
                raise ValueError(f"signal date missing from market data: {ticker} {row['SignalDate']}")
            position = positions[row["SignalDate"]]
            if position - 1 not in buy_positions:
                entries.append(row)
    if not entries:
        return signals.iloc[0:0].copy()
    return pd.DataFrame(entries).reset_index(drop=True)


def _exit_values(market, entry_index, entry_price, horizon):
    exit_index = entry_index + horizon
    if exit_index >= len(market):
        return pd.NaT, float("nan")
    exit_row = market.iloc[exit_index]
    return exit_row["Date"], exit_row["Close"] / entry_price - 1


def build_trade_events(signals, market_data=None):
    entries = identify_entry_signals(signals, market_data=market_data)
    rows = []
    for _, entry in entries.iterrows():
        ticker = entry["Ticker"]
        market = _prepare_market(ticker, market_data)
        matches = market.index[market["Date"] == entry["SignalDate"]]
        if len(matches) != 1:
            raise ValueError(f"entry date is not unique in market data: {ticker}")
        entry_index = int(matches[0])
        entry_price = float(market.at[entry_index, "Close"])
        exits = {
            horizon: _exit_values(market, entry_index, entry_price, horizon)
            for horizon in (5, 20, 60)
        }
        if entry_index + 60 < len(market):
            path_returns = (
                market.loc[entry_index:entry_index + 60, "Close"] / entry_price - 1
            )
            favorable_excursion = path_returns.max()
            adverse_excursion = path_returns.min()
        else:
            favorable_excursion = float("nan")
            adverse_excursion = float("nan")
        rows.append(
            {
                "Ticker": ticker,
                "EntryDate": entry["SignalDate"],
                "EntryPrice": entry_price,
                "EntryFinalScore": entry["FinalScore"],
                "EntryTrendScore": entry["TrendScore"],
                "EntryMomentumScore": entry["MomentumScore"],
                "EntryRSScore": entry["RSScore"],
                "EntryNearHighScore": entry["NearHighScore"],
                "EntryVolumeScore": entry["VolumeScore"],
                "EntryRiskScore": entry["RiskScore"],
                "ExitDate_5D": exits[5][0],
                "ExitDate_20D": exits[20][0],
                "ExitDate_60D": exits[60][0],
                "Return_5D": exits[5][1],
                "Return_20D": exits[20][1],
                "Return_60D": exits[60][1],
                "MaximumFavorableExcursion": favorable_excursion,
                "MaximumAdverseExcursion": adverse_excursion,
            }
        )
    events = pd.DataFrame(rows, columns=EVENT_COLUMNS)
    for column in ("EntryDate", "ExitDate_5D", "ExitDate_20D", "ExitDate_60D"):
        if column in events:
            events[column] = pd.to_datetime(events[column]).dt.strftime("%Y-%m-%d")
    return events


def _maximum_drawdown_proxy(events):
    valid = events.dropna(subset=["Return_20D"])
    if valid.empty:
        return float("nan")
    cohort = valid.groupby("EntryDate")["Return_20D"].mean().sort_index()
    daily_equivalent = (1 + cohort).pow(1 / 20) - 1
    equity = (1 + daily_equivalent).cumprod()
    return float((equity / equity.cummax() - 1).min())


def summarize_trade_events(events):
    summary = {
        "TotalEntries": len(events),
        "SymbolsCount": events["Ticker"].nunique(),
        "AverageEntryScore": events["EntryFinalScore"].mean(),
    }
    for horizon in (5, 20, 60):
        returns = events[f"Return_{horizon}D"].dropna()
        summary.update(
            {
                f"AverageReturn_{horizon}D": returns.mean(),
                f"MedianReturn_{horizon}D": returns.median(),
                f"WinRate_{horizon}D": (returns > 0).mean(),
                f"StdDevReturn_{horizon}D": returns.std(ddof=1),
            }
        )
    summary.update(
        {
            "MaximumDrawdownProxy": _maximum_drawdown_proxy(events),
            "AverageAdverseExcursion": events["MaximumAdverseExcursion"].mean(),
            "AverageFavorableExcursion": events["MaximumFavorableExcursion"].mean(),
        }
    )
    return pd.DataFrame([summary], columns=SUMMARY_COLUMNS)


def run_trade_event_backtest(
    signals_input_path=SIGNALS_INPUT_PATH,
    events_output_path=EVENTS_OUTPUT_PATH,
    summary_output_path=SUMMARY_OUTPUT_PATH,
):
    signals = load_signal_history(signals_input_path)
    events = build_trade_events(signals)
    summary = summarize_trade_events(events)
    events_path = Path(events_output_path)
    summary_path = Path(summary_output_path)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(events_path, index=False)
    summary.to_csv(summary_path, index=False)
    return events, summary


if __name__ == "__main__":
    event_table, summary_table = run_trade_event_backtest()
    print(summary_table.to_string(index=False))
    print(f"Events: {EVENTS_OUTPUT_PATH} ({len(event_table)} rows)")
    print(f"Summary: {SUMMARY_OUTPUT_PATH}")
