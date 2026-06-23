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

    # 日收益率
    df["Return"] = df["Close"].pct_change()

    # 波动率
    volatility = df["Return"].std()

    # 累计最大值
    rolling_max = df["Close"].cummax()

    # 回撤
    drawdown = (
        df["Close"] - rolling_max
    ) / rolling_max

    # 最大回撤
    max_drawdown = drawdown.min()

    # 总收益率
    total_return = (
        df["Close"].iloc[-1]
        / df["Close"].iloc[0]
    ) - 1

    results.append({
        "Ticker": ticker,
        "Total_Return": total_return,
        "Volatility": volatility,
        "Max_Drawdown": max_drawdown
    })

risk_df = pd.DataFrame(results)

# 风险收益排序
risk_df = risk_df.sort_values(
    by="Total_Return",
    ascending=False
)

print("\n===== 风险分析 =====")
print(risk_df)

risk_df.to_csv("risk_analysis.csv", index=False)

print("\n已保存到 risk_analysis.csv")