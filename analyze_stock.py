import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

tickers = ["AAPL", "NVDA", "TSLA", "AMD", "GOOGL"]
data_dir = Path("data")
charts_dir = Path("charts")
charts_dir.mkdir(exist_ok=True)

summary_list = []
for ticker in tickers:
    print(f"\n===== {ticker} =====")

    file_path = data_dir / f"{ticker}.csv"
    df = pd.read_csv(file_path, skiprows=1)

    # 重命名列
    df.columns = ["Date", "Close", "High", "Low", "Open", "Volume"]

    # 转换数据类型
    df["Date"] = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"])
    df["High"] = pd.to_numeric(df["High"])
    df["Low"] = pd.to_numeric(df["Low"])
    df["Open"] = pd.to_numeric(df["Open"])
    df["Volume"] = pd.to_numeric(df["Volume"])

    # 计算日收益率和移动均线
    df["Return"] = df["Close"].pct_change()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    print("平均收盘价：")
    print(df["Close"].mean())

    print("\n最新收盘价：")
    print(df["Close"].iloc[-1])

    print("\n最近5天指标：")
    print(df[["Date", "Close", "Return", "MA20", "MA60"]].tail())

    latest_close = df["Close"].iloc[-1]
    latest_ma20 = df["MA20"].iloc[-1]
    latest_ma60 = df["MA60"].iloc[-1]

    if latest_close > latest_ma20 and latest_ma20 > latest_ma60:
        trend = "强势上涨"
    elif latest_close < latest_ma20 and latest_ma20 < latest_ma60:
        trend = "弱势下跌"
    else:
        trend = "震荡"

    # 绘制收盘价和移动均线
    chart_path = charts_dir / f"{ticker}_chart.png"

    plt.figure(figsize=(12, 6))
    plt.plot(df["Date"], df["Close"], label="Close")
    plt.plot(df["Date"], df["MA20"], label="MA20")
    plt.plot(df["Date"], df["MA60"], label="MA60")
    plt.title(f"{ticker} Close Price with MA20 and MA60")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    print(f"\n图表已保存到 {chart_path}")
    print(f"趋势：{trend}")

    summary = {
        "Ticker": ticker,
        "Latest_Close": latest_close,
        "MA20": latest_ma20,
        "MA60": latest_ma60,
        "Return": df["Return"].iloc[-1],
        "Trend": trend,
    }

    summary_list.append(summary)

summary_df = pd.DataFrame(summary_list)

summary_df.to_csv("summary.csv", index=False)

print("\n===== 汇总表 =====")
print(summary_df)
