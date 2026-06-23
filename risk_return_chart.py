import pandas as pd

import matplotlib.pyplot as plt


df = pd.read_csv("stock_personality.csv")


plt.figure(figsize=(10,6))

plt.scatter(
    df["Annual Volatility %"],
    df["Annual Return %"],
    s=200
)

for i in range(len(df)):

    plt.text(
        df["Annual Volatility %"].iloc[i],
        df["Annual Return %"].iloc[i],
        df["Ticker"].iloc[i]
    )


plt.xlabel("Risk (Volatility %)")

plt.ylabel("Return %")

plt.title("Risk vs Return")

plt.grid()

plt.show()