

import pandas as pd
from report import save_daily_report
from reason import generate_reason
from data_validator import (
    print_validation_summary,
    validate_watchlist,
)
from watchlist import load_watchlist
from stock_loader import load_stock
from indicators import calculate_indicators
from position import calculate_position_size
from score import calculate_rank_score, calculate_final_score
from trade_signal import generate_signals
from config import ACCOUNT_SIZE, RISK_PER_TRADE, STOCK_RANK_OUTPUT, TOP10_OUTPUT


def process_single_stock(ticker):

    df = load_stock(ticker)
    df = calculate_indicators(df)

    latest_date = pd.to_datetime(df["Date"].iloc[-1])
    market_data_date = latest_date.strftime("%Y-%m-%d")

    print(f"{ticker} 最新数据日期: {market_data_date}")

    latest_close = df["Close"].iloc[-1]
    latest_ma20 = df["MA20"].iloc[-1]
    latest_ma60 = df["MA60"].iloc[-1]
    latest_high60 = df["High60"].iloc[-1]
    
    latest_high252 = df["High252"].iloc[-1]
    latest_volume = df["Volume"].iloc[-1]
    latest_volume_ma20 = df["VolumeMA20"].iloc[-1]
    latest_atr = df["ATR14"].iloc[-1]
    latest_rsi = df["RSI14"].iloc[-1]
    latest_macd = df["MACD"].iloc[-1]
    latest_macd_signal = df["MACD_Signal"].iloc[-1]
    latest_hist = df["Histogram"].iloc[-1]

    volume_ratio = (
        latest_volume /
        latest_volume_ma20
    )

    distance_to_high = (
        latest_close
        / latest_high252
    )

    recent_return = (
        df["Close"].iloc[-1]
        /
        df["Close"].iloc[-20]
    ) - 1
    return_60d = (
        df["Close"].iloc[-1]
        /
        df["Close"].iloc[-60]
    ) - 1

    score, confidence = calculate_rank_score(
        latest_close,
        latest_ma20,
        latest_ma60,
        recent_return,
        return_60d,
        volume_ratio,
        latest_high60,
        distance_to_high,
        latest_macd,
        latest_macd_signal,
        latest_hist
    )
    position_size, rsi_position_factor = calculate_position_size(
        latest_atr,
        latest_rsi,
        ACCOUNT_SIZE,
        RISK_PER_TRADE
    )
    return {
        "Ticker": ticker,
        "MarketDataDate": market_data_date,
        "Close": latest_close,
        "MA20": latest_ma20,
        "MA60": latest_ma60,
        "ATR14": latest_atr,
        "RSI14": latest_rsi,
        "MACD": latest_macd,
        "MACD_Signal": latest_macd_signal,
        "Histogram": latest_hist,
        "RSI_Position_Factor": rsi_position_factor,
        "StopLoss": latest_close - latest_atr * 2,
        "RiskPerShare": latest_atr * 2,
        "PositionSize": int(position_size),
        "PositionValue": int(position_size * latest_close),
        "PortfolioPct":position_size * latest_close / ACCOUNT_SIZE * 100,
        "20Day_Return": recent_return,
        "60Day_Return": return_60d,
        "Volume_Ratio": volume_ratio,
        "DistanceToHigh": distance_to_high,
        "Score": score,
        "Confidence": confidence
    }
    
    

def rank_stocks(tickers):

    results = []

    for ticker in tickers:
        try:
            result = process_single_stock(ticker)
            results.append(result)
        except Exception as e:
            print(f"跳过 {ticker}，原因：{e}")

    rank_df = pd.DataFrame(results)

    rank_df = calculate_final_score(rank_df)

    rank_df = generate_signals(rank_df)
    rank_df["Reason"] = rank_df.apply(generate_reason, axis=1)

    rank_df = rank_df.sort_values(
        by="FinalScore",
        ascending=False
    )

    return rank_df
def print_signal_summary(rank_df):
    buy_df = rank_df[rank_df["TradeSignal"] == "BUY"]
    watch_df = rank_df[rank_df["TradeSignal"] == "WATCH"]

    print("\n===== Today's BUY LIST =====")
    if buy_df.empty:
        print("无")
    else:
        for _, row in buy_df.iterrows():
            print("=" * 30)
            print(f"{'Ticker':<15}: {row['Ticker']}")
            print("=" * 30)
            print(f"{'Price':<15}: {row['Close']:.2f}")
            print(f"{'Final Score':<15}: {row['FinalScore']:.2f}")
            print(f"{'Confidence':<15}: {row['Confidence']} / 100")
            print(f"{'Position Size':<15}: {row['PositionSize']} shares")
            print(f"{'Stop Loss':<15}: {row['StopLoss']:.2f}")
            print(f"{'ATR(14)':<15}: {row['ATR14']:.2f}")
            print(f"{'MACD':<15}: {row['MACD']:.2f}")
            print(f"{'MACD Histogram':<15}: {row['Histogram']:.2f}")
            print("\nReasons")
            for reason in row["Reason"].split(" | "):
                print(f"   ✓ {reason}")
            print("-" * 50)

    print("\n===== Today's WATCH LIST =====")
    if watch_df.empty:
        print("无")
    else:
        for _, row in watch_df.iterrows():
            print("=" * 30)
            print(f"{'Ticker':<15}: {row['Ticker']}")
            print("=" * 30)
            print(f"{'Price':<15}: {row['Close']:.2f}")
            print(f"{'Final Score':<15}: {row['FinalScore']:.2f}")
            print(f"{'Confidence':<15}: {row['Confidence']} / 100")
            print(f"{'Distance High':<15}: {row['DistanceToHigh']:.1%}")
            print(f"{'Volume Ratio':<15}: {row['Volume_Ratio']:.2f}x")
            print(f"{'RSI(14)':<15}: {row['RSI14']:.1f}")
            print(f"{'MACD':<15}: {row['MACD']:.2f}")
            print(f"{'MACD Histogram':<15}: {row['Histogram']:.2f}")
            print("\nReasons")
            for reason in row["Reason"].split(" | "):
                print(f"   ✓ {reason}")
            print("-" * 50)

if __name__ == "__main__":

    validation_results, universe_latest_date = (
        validate_watchlist()
    )

    print_validation_summary(
        validation_results,
        universe_latest_date,
    )

    tickers = [
    result["Ticker"]
    for result in validation_results
    if result["IsValid"]
    ]

    if not tickers:
        raise RuntimeError(
            "No valid stock data available for ranking."
        )

    rank_df = rank_stocks(tickers)

    print("\n===== TOP 10 STOCK RANKING =====")
    print(rank_df.head(10))
    print_signal_summary(rank_df)

    rank_df.to_csv(STOCK_RANK_OUTPUT, index=False)
    save_daily_report(rank_df)
    top10_df = rank_df.head(10)

    top10_df.to_csv(
    TOP10_OUTPUT,
    index=False
)

    print(f"\n已保存到 {STOCK_RANK_OUTPUT}")

