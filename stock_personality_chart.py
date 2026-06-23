import pandas as pd

import matplotlib.pyplot as plt


df = pd.read_csv("results/stock_personality.csv")

plt.figure(figsize=(10,6))

plt.bar(
    df["Ticker"],
    df["Sharpe"]
)

plt.title("Sharpe Ratio Comparison")

plt.xlabel("Ticker")

plt.ylabel("Sharpe Ratio")

plt.grid()

plt.show()

plt.figure(figsize=(10,6))

plt.bar(
    df["Ticker"],
    df["Annual Return %"]
)

plt.title("Annual Return Comparison")

plt.xlabel("Ticker")

plt.ylabel("Annual Return %")

plt.grid()

plt.show()

plt.figure(figsize=(10,6))

plt.bar(
    df["Ticker"],
    df["Max Drawdown %"]
)

plt.title("Max Drawdown Comparison")

plt.xlabel("Ticker")

plt.ylabel("Drawdown %")

plt.grid()

plt.show()