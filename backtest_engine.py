import pandas as pd

from stock_loader import load_stock
from indicators import calculate_indicators


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


if __name__ == "__main__":
    print_entry_signal_summary("AMD")