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
    df = add_forward_returns(df)

    return df


def summarize_buy_signals(buy_df):
    if buy_df.empty:
        return {
            "BuySignalCount": 0,
            "Avg5DReturn": None,
            "Avg20DReturn": None,
            "Avg60DReturn": None,
            "WinRate5D": None,
            "WinRate20D": None,
            "WinRate60D": None,
        }

    valid_5d = buy_df["Forward_5D_Return"].dropna()
    valid_20d = buy_df["Forward_20D_Return"].dropna()
    valid_60d = buy_df["Forward_60D_Return"].dropna()

    return {
        "BuySignalCount": len(buy_df),
        "Avg5DReturn": valid_5d.mean(),
        "Avg20DReturn": valid_20d.mean(),
        "Avg60DReturn": valid_60d.mean(),
        "WinRate5D": (valid_5d > 0).mean(),
        "WinRate20D": (valid_20d > 0).mean(),
        "WinRate60D": (valid_60d > 0).mean(),
    }


def print_buy_signal_summary(ticker):
    df = prepare_backtest_data(ticker)

    buy_df = df[df["TradeSignal"] == "BUY"].copy()

    output_path = f"results/backtest_signals_{ticker}.csv"
    buy_df.to_csv(output_path, index=False)

    summary = summarize_buy_signals(buy_df)

    print("\n" + "=" * 70)
    print(f"BACKTEST SIGNAL SUMMARY: {ticker}")
    print("=" * 70)

    print(f"Total Rows       : {len(df)}")
    print(f"BUY Signal Count : {summary['BuySignalCount']}")

    if buy_df.empty:
        print("No historical BUY signals found.")
        return

    print("\nForward return summary:")

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

    print(f"\nSaved to {output_path}")

    print("\nRecent BUY signals:")
    print(
        buy_df[
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
            ]
        ].tail(10)
    )


if __name__ == "__main__":
    print_buy_signal_summary("AMD")