

import pandas as pd
from watchlist import load_watchlist
from stock_loader import load_stock
from indicators import calculate_indicators
from position import calculate_position_size
from score import calculate_rank_score, calculate_final_score
from trade_signal import generate_signals

tickers = load_watchlist()
ACCOUNT_SIZE = 100000
RISK_PER_TRADE = 0.01

def process_single_stock(ticker):

    df = load_stock(ticker)
    df = calculate_indicators(df)

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
    latest_signal = df["Signal"].iloc[-1]
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
        latest_signal,
        latest_hist
    )
    position_size, rsi_position_factor = calculate_position_size(
        latest_atr,
        latest_rsi,
        ACCOUNT_SIZE,
        RISK_PER_TRADE
    )
    return{
        "Ticker": ticker,
        "Close": latest_close,
        "MA20": latest_ma20,
        "MA60": latest_ma60,
        "ATR14": latest_atr,
        "RSI14": latest_rsi,
        "MACD": latest_macd,
        "Signal": latest_signal,
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

        result = process_single_stock(ticker)
        results.append(result)

    rank_df = pd.DataFrame(results)

    rank_df = calculate_final_score(rank_df)

    rank_df = generate_signals(rank_df)

    rank_df = rank_df.sort_values(
        by="FinalScore",
        ascending=False
    )

    return rank_df


if __name__ == "__main__":

    tickers = load_watchlist()

    rank_df = rank_stocks(tickers)

    print("\n===== 股票评分排名 =====")
    print(rank_df.head(10))

    rank_df.to_csv("results/stock_rank.csv", index=False)

    top10_df = rank_df.head(10)

    top10_df.to_csv(
    "results/top10.csv",
    index=False
)

    print("\n已保存到 results/stock_rank.csv")

