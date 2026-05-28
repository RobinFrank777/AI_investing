import pandas as pd
from pathlib import Path

tickers = ["AAPL", "NVDA", "TSLA", "AMD", "GOOGL"]

data_dir = Path("data")

results = []

for ticker in tickers:

    file_path = data_dir / f"{ticker}.csv"

    df = pd.read_csv(file_path, skiprows=1)

    df.columns = ["Date", "Close", "High", "Low", "Open", "Volume"]

    df["Close"] = pd.to_numeric(df["Close"])

    # 计算均线
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    latest_close = df["Close"].iloc[-1]
    latest_ma20 = df["MA20"].iloc[-1]
    latest_ma60 = df["MA60"].iloc[-1]

    score = 0

    # 条件1：站上MA20
    if latest_close > latest_ma20:
        score += 30

    # 条件2：MA20在MA60上方
    if latest_ma20 > latest_ma60:
        score += 30

    # 条件3：最近涨幅
    recent_return = (
        df["Close"].iloc[-1] /
        df["Close"].iloc[-20]
    ) - 1

    if recent_return > 0.10:
        score += 40

    results.append({
        "Ticker": ticker,
        "Close": latest_close,
        "MA20": latest_ma20,
        "MA60": latest_ma60,
        "20Day_Return": recent_return,
        "Score": score
    })

# 转成DataFrame
rank_df = pd.DataFrame(results)

# 按分数排序
rank_df = rank_df.sort_values(
    by="Score",
    ascending=False
)

print("\n===== 股票评分排名 =====")
print(rank_df)

# 保存
rank_df.to_csv("stock_rank.csv", index=False)

print("\n已保存到 stock_rank.csv")