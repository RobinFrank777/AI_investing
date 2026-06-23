import pandas as pd
import numpy as np
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

    # 年化收益率
    annual_return = (
        df["Return"].mean()
    ) * 252

    # 年化波动率
    annual_volatility = (
        df["Return"].std()
    ) * np.sqrt(252)

    # 夏普比率
    sharpe_ratio = (
        annual_return / annual_volatility
    )

    results.append({
        "Ticker": ticker,
        "Annual_Return": annual_return,
        "Annual_Volatility": annual_volatility,
        "Sharpe_Ratio": sharpe_ratio
    })

sharpe_df = pd.DataFrame(results)

# 夏普比率排序
sharpe_df = sharpe_df.sort_values(
    by="Sharpe_Ratio",
    ascending=False
)

print("\n===== 夏普比率分析 =====")
print(sharpe_df)

sharpe_df.to_csv("sharpe_analysis.csv", index=False)

print("\n已保存到 sharpe_analysis.csv")