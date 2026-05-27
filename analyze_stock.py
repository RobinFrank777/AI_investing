import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# 读取CSV
df = pd.read_csv("data/AAPL.csv", skiprows=1)

# 重命名列
df.columns = ["Date", "Close", "High", "Low", "Open", "Volume"]

print("前5行数据：")
print(df.head())

print("\n数据类型：")
print(df.dtypes)

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

print("\n收盘价平均值：")
print(df["Close"].mean())

print("\n最高收盘价：")
print(df["Close"].max())

print("\n最低收盘价：")
print(df["Close"].min())

print("\n基本统计：")
print(df.describe())

print("\n最近5天指标：")
print(df[["Close", "Return", "MA20", "MA60"]].tail())

# 绘制收盘价和移动均线
charts_dir = Path("charts")
charts_dir.mkdir(exist_ok=True)

plt.figure(figsize=(12, 6))
plt.plot(df["Date"], df["Close"], label="Close")
plt.plot(df["Date"], df["MA20"], label="MA20")
plt.plot(df["Date"], df["MA60"], label="MA60")
plt.title("AAPL Close Price with MA20 and MA60")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(charts_dir / "AAPL_ma_chart.png")
plt.close()

print("\n图表已保存到 charts/AAPL_ma_chart.png")
