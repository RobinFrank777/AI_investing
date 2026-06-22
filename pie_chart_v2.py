import pandas as pd
import matplotlib.pyplot as plt

result_df = pd.read_csv("ranking.csv")

labels = result_df["Ticker"]

sizes = result_df["Market Value"]

plt.figure(figsize=(8,8))

plt.pie(
    sizes,
    labels=labels,
    autopct="%1.1f%%"
)


plt.title("Portfolio Allocation")

plt.savefig("charts/allocation.png")

plt.show()