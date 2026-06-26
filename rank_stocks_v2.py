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
    latest_high60,
    distance_to_high
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

    if distance_to_high >= 0.95:
        score += 30
    elif distance_to_high >= 0.90:
        score += 20
    elif distance_to_high >= 0.80:
        score += 10

    return score

import pandas as pd
from stock_loader import load_stock
from indicators import calculate_indicators

tickers = load_watchlist()
ACCOUNT_SIZE = 100000
RISK_PER_TRADE = 0.01

def rank_stocks(tickers):

    results = []

    for ticker in tickers:

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

        score = calculate_rank_score(
            latest_close,
            latest_ma20,
            latest_ma60,
            recent_return,
            return_60d,
            volume_ratio,
            latest_high60,
            distance_to_high
        )
        risk_dollar = ACCOUNT_SIZE * RISK_PER_TRADE
        position_size = risk_dollar / (latest_atr * 2)
        if latest_rsi < 60:
            rsi_position_factor = 1.0
        elif latest_rsi < 75:
            rsi_position_factor = 0.8
        else:
            rsi_position_factor = 0.5

        position_size = position_size * rsi_position_factor

        results.append({
            "Ticker": ticker,
            "Close": latest_close,
            "MA20": latest_ma20,
            "MA60": latest_ma60,
            "ATR14": latest_atr,
            "RSI14": latest_rsi,
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
            "Score": score
        })

    rank_df = pd.DataFrame(results)

    rank_df["RS_Score"] = (
    rank_df["60Day_Return"]
    .rank(pct=True)
    * 100
    )

    rank_df["NearHighScore"] = 0

    rank_df.loc[
        rank_df["DistanceToHigh"] >= 1.00,
        "NearHighScore"
    ] = 40

    rank_df.loc[
        (rank_df["DistanceToHigh"] >= 0.98) &
        (rank_df["DistanceToHigh"] < 1.00),
        "NearHighScore"
    ] = 30

    rank_df.loc[
        (rank_df["DistanceToHigh"] >= 0.95) &
        (rank_df["DistanceToHigh"] < 0.98),
        "NearHighScore"
    ] = 20

    rank_df.loc[
        (rank_df["DistanceToHigh"] >= 0.90) &
        (rank_df["DistanceToHigh"] < 0.95),
        "NearHighScore"
    ] = 10

    rank_df["FinalScore"] = (
        rank_df["Score"] * 0.7
        + rank_df["RS_Score"] * 0.2
        + rank_df["NearHighScore"] * 0.1
    )

    rank_df["Signal"] = "IGNORE"

    rank_df.loc[
        rank_df["FinalScore"] >= 120,
        "Signal"
    ] = "WATCH"

    rank_df.loc[
        (rank_df["FinalScore"] >= 145) &
        (rank_df["Volume_Ratio"] > 0.8) &
        (rank_df["DistanceToHigh"] >= 0.95)&
        (rank_df["Close"] > rank_df["MA20"]) &
        (rank_df["MA20"] > rank_df["MA60"]),
        "Signal"
    ] = "BUY"

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

