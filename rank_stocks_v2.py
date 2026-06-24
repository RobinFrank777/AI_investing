def load_watchlist():

    df = pd.read_csv("data/watchlist.csv")

    return df["Ticker"].tolist()

def calculate_rank_score(
    latest_close,
    latest_ma20,
    latest_ma60,
    recent_return,
    return_60d,
    volume_ratio,
    latest_high60
):

    score = 0

    if latest_close > latest_ma20:
        score += 30

    if latest_ma20 > latest_ma60:
        score += 30

    score += recent_return * 70
    score += return_60d * 30
    if volume_ratio > 1.5:
        score += 20
    if latest_close > latest_high60:
        score += 20
    return score

import pandas as pd
from stock_loader import load_stock

tickers = load_watchlist()

def rank_stocks(tickers):

    results = []

    for ticker in tickers:

        df = load_stock(ticker)

        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA60"] = df["Close"].rolling(window=60).mean()
        df["High60"] = (
            df["Close"]
            .shift(1)
            .rolling(window=60)
            .max()
        )
        df["VolumeMA20"] = df["Volume"].rolling(window=20).mean()

        latest_close = df["Close"].iloc[-1]
        latest_ma20 = df["MA20"].iloc[-1]
        latest_ma60 = df["MA60"].iloc[-1]
        latest_high60 = df["High60"].iloc[-1]
        latest_volume = df["Volume"].iloc[-1]
        latest_volume_ma20 = df["VolumeMA20"].iloc[-1]

        volume_ratio = (
            latest_volume /
            latest_volume_ma20
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

        score = calculate_rank_score(
            latest_close,
            latest_ma20,
            latest_ma60,
            recent_return,
            return_60d,
            volume_ratio,
            latest_high60
        )

        results.append({
            "Ticker": ticker,
            "Close": latest_close,
            "MA20": latest_ma20,
            "MA60": latest_ma60,
            "20Day_Return": recent_return,
            "60Day_Return": return_60d,
            "Volume_Ratio": volume_ratio,
            "Score": score
        })

    rank_df = pd.DataFrame(results)

    rank_df = rank_df.sort_values(
        by="Score",
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

