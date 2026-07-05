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

    return df


def print_buy_signal_summary(ticker):
    df = prepare_backtest_data(ticker)

    buy_df = df[df["TradeSignal"] == "BUY"]

    print("\n" + "=" * 70)
    print(f"BACKTEST SIGNAL SUMMARY: {ticker}")
    print("=" * 70)

    print(f"Total Rows       : {len(df)}")
    print(f"BUY Signal Count : {len(buy_df)}")

    if buy_df.empty:
        print("No historical BUY signals found.")
        return

    print("\nRecent BUY signals:")
    print(
        buy_df[
            [
                "Date",
                "Close",
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