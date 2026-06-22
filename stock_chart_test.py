import matplotlib.pyplot as plt
from stock_loader import load_stock

ticker = "TSLA"
df = load_stock(ticker)

df["MA30"] = df["Close"].rolling(30).mean()

df["MA60"] = df["Close"].rolling(60).mean()

df["Signal"] = ""

for i in range(1, len(df)):
    yesterday_ma30 = df["MA30"].iloc[i-1]
    yesterday_ma60 = df["MA60"].iloc[i-1]

    today_ma30 = df["MA30"].iloc[i]
    today_ma60 = df["MA60"].iloc[i]

    if (
        yesterday_ma30 < yesterday_ma60
        and
        today_ma30 > today_ma60
    ):
        df.loc[i, "Signal"] = "BUY"
    elif (
        yesterday_ma30 > yesterday_ma60
        and
        today_ma30 < today_ma60
    ):
        df.loc[i, "Signal"] = "SELL"
    
    signals = df[df["Signal"] != ""]

print(signals[["Date", "Signal"]])

plt.figure(figsize=(10, 5))

plt.plot(
    df["Date"],
    df["Close"],
    label="Close Price"
)

buy_signals = df[df["Signal"] == "BUY"]
sell_signals = df[df["Signal"] == "SELL"]

plt.scatter(
    buy_signals["Date"],
    buy_signals["Close"],
    marker="^",
    s=120,
    label="BUY"
)

plt.scatter(
    sell_signals["Date"],
    sell_signals["Close"],
    marker="v",
    s=120,
    label="SELL"
)

plt.plot(
    df["Date"],
    df["MA30"],
    label="MA30"
)

plt.plot(
    df["Date"],
    df["MA60"],
    label="MA60"
)

plt.title(f"{ticker} Close Price")

plt.xlabel("Date")

plt.ylabel("Close Price")

plt.legend()

plt.xticks(df["Date"][::30], rotation=45)


plt.tight_layout()

plt.savefig(f"charts/{ticker}_line.png")

plt.show()