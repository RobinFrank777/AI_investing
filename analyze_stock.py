import pandas as pd

# 读取CSV
df = pd.read_csv("data/AAPL.csv", skiprows=1)

# 重命名列
df.columns = ["Date", "Close", "High", "Low", "Open", "Volume"]

print("前5行数据：")
print(df.head())

print("\n数据类型：")
print(df.dtypes)

# 转换数据类型
df["Close"] = pd.to_numeric(df["Close"])
df["High"] = pd.to_numeric(df["High"])
df["Low"] = pd.to_numeric(df["Low"])
df["Open"] = pd.to_numeric(df["Open"])
df["Volume"] = pd.to_numeric(df["Volume"])

print("\n收盘价平均值：")
print(df["Close"].mean())

print("\n最高收盘价：")
print(df["Close"].max())

print("\n最低收盘价：")
print(df["Close"].min())

print("\n基本统计：")
print(df.describe())
