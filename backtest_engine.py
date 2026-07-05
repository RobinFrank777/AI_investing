import pandas as pd

from stock_loader import load_stock
from indicators import calculate_indicators
from watchlist import load_watchlist
MIN_COMPLETED_TRADES = 10
MIN_AVERAGE_RETURN = 0
MIN_WIN_RATE = 0.5
TRADE_COUNT_CAP = 30

def generate_historical_trade_signals(df):
    df = df.copy()

    df["TradeSignal"] = "IGNORE"

    watch_condition = (
        df["Close"].notna()
        & df["MA20"].notna()
        & df["MA60"].notna()
        & df["Volume_Ratio"].notna()
        & df["DistanceToHigh"].notna()
    )

    df.loc[
        watch_condition,
        "TradeSignal",
    ] = "WATCH"

    buy_condition = (
        (df["Close"] > df["MA20"])
        & (df["MA20"] > df["MA60"])
        & (df["Volume_Ratio"] > 0.8)
        & (df["DistanceToHigh"] >= 0.95)
    )

    df.loc[
        buy_condition,
        "TradeSignal",
    ] = "BUY"

    return df


def add_entry_signals(df):
    df = df.copy()

    previous_signal = df["TradeSignal"].shift(1)

    df["EntrySignal"] = (
        (df["TradeSignal"] == "BUY")
        & (previous_signal != "BUY")
    )

    return df


def add_forward_returns(df):
    df = df.copy()

    df["Forward_5D_Close"] = df["Close"].shift(-5)
    df["Forward_20D_Close"] = df["Close"].shift(-20)
    df["Forward_60D_Close"] = df["Close"].shift(-60)

    df["Forward_5D_Return"] = (
        df["Forward_5D_Close"] / df["Close"] - 1
    )

    df["Forward_20D_Return"] = (
        df["Forward_20D_Close"] / df["Close"] - 1
    )

    df["Forward_60D_Return"] = (
        df["Forward_60D_Close"] / df["Close"] - 1
    )

    return df

def build_fixed_holding_trades(df, holding_days=20):
    trades = []

    entry_df = df[df["EntrySignal"]].copy()

    for entry_index, entry_row in entry_df.iterrows():
        exit_index = entry_index + holding_days

        if exit_index >= len(df):
            continue

        exit_row = df.iloc[exit_index]

        entry_price = entry_row["Close"]
        exit_price = exit_row["Close"]

        trade_return = exit_price / entry_price - 1

        trades.append(
            {
                "Ticker": entry_row.get("Ticker", None),
                "EntryDate": entry_row["Date"],
                "EntryPrice": entry_price,
                "ExitDate": exit_row["Date"],
                "ExitPrice": exit_price,
                "HoldingDays": holding_days,
                "Return": trade_return,
            }
        )

    return pd.DataFrame(trades)

def prepare_backtest_data(ticker):
    df = load_stock(ticker)
    df = calculate_indicators(df)

    df["Volume_Ratio"] = (
        df["Volume"] / df["VolumeMA20"]
    )

    df["DistanceToHigh"] = (
        df["Close"] / df["High252"]
    )

    df = generate_historical_trade_signals(df)
    df = add_entry_signals(df)
    df = add_forward_returns(df)
    df["Ticker"] = ticker
    return df


def summarize_entries(entry_df):
    if entry_df.empty:
        return {
            "EntrySignalCount": 0,
            "Avg5DReturn": None,
            "Avg20DReturn": None,
            "Avg60DReturn": None,
            "WinRate5D": None,
            "WinRate20D": None,
            "WinRate60D": None,
        }

    valid_5d = entry_df["Forward_5D_Return"].dropna()
    valid_20d = entry_df["Forward_20D_Return"].dropna()
    valid_60d = entry_df["Forward_60D_Return"].dropna()

    return {
        "EntrySignalCount": len(entry_df),
        "Avg5DReturn": valid_5d.mean(),
        "Avg20DReturn": valid_20d.mean(),
        "Avg60DReturn": valid_60d.mean(),
        "WinRate5D": (valid_5d > 0).mean(),
        "WinRate20D": (valid_20d > 0).mean(),
        "WinRate60D": (valid_60d > 0).mean(),
    }


def print_entry_signal_summary(ticker):
    df = prepare_backtest_data(ticker)

    buy_df = df[df["TradeSignal"] == "BUY"].copy()
    entry_df = df[df["EntrySignal"]].copy()

    signal_output_path = f"results/backtest_signals_{ticker}.csv"
    entry_output_path = f"results/backtest_entries_{ticker}.csv"
    trades_output_path = f"results/backtest_trades_{ticker}_20d.csv"

    buy_df.to_csv(signal_output_path, index=False)
    entry_df.to_csv(entry_output_path, index=False)

    trades_df = build_fixed_holding_trades(
        df,
        holding_days=20,
    )

    trades_df.to_csv(trades_output_path, index=False)

    summary = summarize_entries(entry_df)

    print("\n" + "=" * 70)
    print(f"BACKTEST ENTRY SUMMARY: {ticker}")
    print("=" * 70)

    print(f"Total Rows        : {len(df)}")
    print(f"BUY Signal Days   : {len(buy_df)}")
    print(f"Entry Signal Count: {summary['EntrySignalCount']}")

    if entry_df.empty:
        print("No historical entry signals found.")
        return

    print("\nForward return summary based on entry signals:")

    print(
        f"Average 5D Return  : "
        f"{summary['Avg5DReturn']:.2%}"
    )

    print(
        f"Average 20D Return : "
        f"{summary['Avg20DReturn']:.2%}"
    )

    print(
        f"Average 60D Return : "
        f"{summary['Avg60DReturn']:.2%}"
    )

    print(
        f"5D Win Rate        : "
        f"{summary['WinRate5D']:.1%}"
    )

    print(
        f"20D Win Rate       : "
        f"{summary['WinRate20D']:.1%}"
    )

    print(
        f"60D Win Rate       : "
        f"{summary['WinRate60D']:.1%}"
    )

    print(f"\nSaved signal days to {signal_output_path}")
    print(f"Saved entry signals to {entry_output_path}")
    print(f"Saved 20D trades to {trades_output_path}")

    if not trades_df.empty:
        print("\n20D fixed holding trade summary:")
        print(f"Trade Count        : {len(trades_df)}")
        print(f"Average Return     : {trades_df['Return'].mean():.2%}")
        print(f"Win Rate           : {(trades_df['Return'] > 0).mean():.1%}")
        print(f"Best Trade         : {trades_df['Return'].max():.2%}")
        print(f"Worst Trade        : {trades_df['Return'].min():.2%}")
    else:
        print("\nNo completed 20D trades found.")

    print("\nRecent entry signals:")
    print(
        entry_df[
            [
                "Date",
                "Close",
                "Forward_5D_Return",
                "Forward_20D_Return",
                "Forward_60D_Return",
                "MA20",
                "MA60",
                "Volume_Ratio",
                "DistanceToHigh",
                "RSI14",
                "MACD",
                "MACD_Signal",
                "Histogram",
                "TradeSignal",
                "EntrySignal",
            ]
        ].tail(10)
    )

def summarize_fixed_holding_trades(trades_df):
    if trades_df.empty:
        return {
            "CompletedTradeCount": 0,
            "AverageReturn": None,
            "WinRate": None,
            "BestTrade": None,
            "WorstTrade": None,
        }

    return {
        "CompletedTradeCount": len(trades_df),
        "AverageReturn": trades_df["Return"].mean(),
        "WinRate": (trades_df["Return"] > 0).mean(),
        "BestTrade": trades_df["Return"].max(),
        "WorstTrade": trades_df["Return"].min(),
    }


def backtest_single_stock(ticker, holding_days=20):
    df = prepare_backtest_data(ticker)

    buy_df = df[df["TradeSignal"] == "BUY"].copy()
    entry_df = df[df["EntrySignal"]].copy()

    trades_df = build_fixed_holding_trades(
        df,
        holding_days=holding_days,
    )

    trade_summary = summarize_fixed_holding_trades(trades_df)

    summary = {
        "Ticker": ticker,
        "TotalRows": len(df),
        "BuySignalDays": len(buy_df),
        "EntrySignalCount": len(entry_df),
        "CompletedTradeCount": trade_summary["CompletedTradeCount"],
        "AverageReturn": trade_summary["AverageReturn"],
        "WinRate": trade_summary["WinRate"],
        "BestTrade": trade_summary["BestTrade"],
        "WorstTrade": trade_summary["WorstTrade"],
        "Error": "",
    }

    return summary, trades_df


def backtest_watchlist(holding_days=20):
    tickers = load_watchlist()

    summaries = []
    all_trades = []

    print("\n" + "=" * 70)
    print(f"BATCH BACKTEST: {holding_days}D FIXED HOLDING")
    print("=" * 70)

    for ticker in tickers:
        try:
            summary, trades_df = backtest_single_stock(
                ticker,
                holding_days=holding_days,
            )

            summaries.append(summary)

            if not trades_df.empty:
                all_trades.append(trades_df)

            print(
                f"{ticker:<8} "
                f"Entries: {summary['EntrySignalCount']:<4} "
                f"Trades: {summary['CompletedTradeCount']:<4} "
                f"Avg: {summary['AverageReturn'] if summary['AverageReturn'] is not None else 0:.2%} "
                f"Win: {summary['WinRate'] if summary['WinRate'] is not None else 0:.1%}"
            )

        except Exception as error:
            summaries.append(
                {
                    "Ticker": ticker,
                    "TotalRows": 0,
                    "BuySignalDays": 0,
                    "EntrySignalCount": 0,
                    "CompletedTradeCount": 0,
                    "AverageReturn": None,
                    "WinRate": None,
                    "BestTrade": None,
                    "WorstTrade": None,
                    "Error": str(error),
                }
            )

            print(f"{ticker:<8} ERROR: {error}")

    summary_df = pd.DataFrame(summaries)

    summary_df["AverageReturn"] = pd.to_numeric(
        summary_df["AverageReturn"],
        errors="coerce",
    )

    summary_df["WinRate"] = pd.to_numeric(
        summary_df["WinRate"],
        errors="coerce",
    )

    summary_df["BestTrade"] = pd.to_numeric(
        summary_df["BestTrade"],
        errors="coerce",
    )

    summary_df["WorstTrade"] = pd.to_numeric(
        summary_df["WorstTrade"],
        errors="coerce",
    )

    summary_df["IsQualified"] = (
        (summary_df["CompletedTradeCount"] >= MIN_COMPLETED_TRADES)
        & (summary_df["AverageReturn"] > MIN_AVERAGE_RETURN)
        & (summary_df["WinRate"] >= MIN_WIN_RATE)
        & (summary_df["Error"] == "")
    )
    summary_df["AverageReturnScore"] = (
        summary_df["AverageReturn"]
        .fillna(0)
        .clip(lower=-0.20, upper=0.30)
        * 100
    )

    summary_df["WinRateScore"] = (
        summary_df["WinRate"]
        .fillna(0)
        * 40
    )

    summary_df["TradeCountScore"] = (
        summary_df["CompletedTradeCount"]
        .clip(upper=TRADE_COUNT_CAP)
        / TRADE_COUNT_CAP
        * 20
    )

    summary_df["RiskScore"] = (
        (1 + summary_df["WorstTrade"].fillna(-1))
        .clip(lower=0, upper=1)
        * 10
    )

    summary_df["BacktestScore"] = (
        summary_df["AverageReturnScore"]
        + summary_df["WinRateScore"]
        + summary_df["TradeCountScore"]
        + summary_df["RiskScore"]
    )


    summary_df = summary_df.sort_values(
        by=["AverageReturn", "WinRate"],
        ascending=False,
        na_position="last",
    )

    summary_output_path = f"results/backtest_summary_{holding_days}d.csv"
    summary_df.to_csv(summary_output_path, index=False)

    qualified_df = summary_df[summary_df["IsQualified"]].copy()

    qualified_df = qualified_df.sort_values(
    by=["BacktestScore", "AverageReturn", "WinRate"],
    ascending=False,
    na_position="last",
    )

    qualified_output_path = f"results/backtest_qualified_{holding_days}d.csv"
    qualified_df.to_csv(qualified_output_path, index=False)

    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=True)
    else:
        all_trades_df = pd.DataFrame()

    trades_output_path = f"results/backtest_all_trades_{holding_days}d.csv"
    all_trades_df.to_csv(trades_output_path, index=False)

    print("\n" + "=" * 70)
    print("BATCH BACKTEST SUMMARY")
    print("=" * 70)

    print(f"Stocks Tested      : {len(summary_df)}")
    print(f"Qualified Stocks   : {len(qualified_df)}")
    print(f"Total Trades       : {len(all_trades_df)}")
    print(f"Saved Summary To   : {summary_output_path}")
    print(f"Saved Qualified To : {qualified_output_path}")
    print(f"Saved Trades To    : {trades_output_path}")

    print("\nTop 10 by Average Return:")
    print(
        summary_df[
            [
                "Ticker",
                "EntrySignalCount",
                "CompletedTradeCount",
                "AverageReturn",
                "WinRate",
                "BestTrade",
                "WorstTrade",
                "IsQualified",
                "BacktestScore",
                "Error",
            ]
        ].head(10)
    )

    print("\nQualified Top 10 by BacktestScore:")
    print(
        qualified_df[
            [
                "Ticker",
                "EntrySignalCount",
                "CompletedTradeCount",
                "AverageReturn",
                "WinRate",
                "BestTrade",
                "WorstTrade",
                "BacktestScore",
                "IsQualified",
            ]
        ].head(10)
    )

    return summary_df, all_trades_df

if __name__ == "__main__":
    backtest_watchlist(holding_days=20)