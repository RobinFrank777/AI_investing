import pandas as pd
import matplotlib.pyplot as plt

from stock_loader import load_stock


portfolio_df = pd.read_csv("portfolio.csv")


for i in range(len(portfolio_df)):

    ticker = portfolio_df.iloc[i]["Ticker"]

    print("生成:", ticker)

    df = load_stock(ticker)

    plt.figure(figsize=(10, 5))

    plt.plot(df["Date"], df["Close"])

    plt.title(f"{ticker} Close Price")

    plt.xlabel("Date")

    plt.ylabel("Close Price")

    plt.xticks(df["Date"][::30], rotation=45)

    plt.tight_layout()

    plt.savefig(f"charts/{ticker}_line.png")

    plt.close()

print("全部图表生成完成")