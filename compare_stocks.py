import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from stock_loader import load_stock

tickers = ["AAPL", "NVDA", "TSLA", "AMD", "GOOGL"]

charts_dir = Path("charts")
charts_dir.mkdir(exist_ok=True)

combined_df = pd.DataFrame()

for ticker in tickers:

    df = load_stock(ticker)

    df["Date"] = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"])

    # 使用日期作为索引
    df.set_index("Date", inplace=True)

    # 归一化价格
    normalized = df["Close"] / df["Close"].iloc[0]

    combined_df[ticker] = normalized

print(combined_df.tail())

# 绘图
plt.figure(figsize=(14, 7))

for ticker in tickers:
    plt.plot(combined_df.index,
             combined_df[ticker],
             label=ticker)

plt.title("Normalized Stock Performance")
plt.xlabel("Date")
plt.ylabel("Normalized Return")
plt.legend()
plt.grid(True)

chart_path = charts_dir / "compare_chart.png"

plt.savefig(chart_path)

print(f"\n对比图已保存到: {chart_path}")
