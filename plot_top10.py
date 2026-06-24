import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results/top10.csv")

plt.figure(figsize=(10, 6))

plt.bar(
    df["Ticker"],
    df["Score"]
)

plt.title("Top 10 Stocks")

plt.xlabel("Ticker")

plt.ylabel("Score")

plt.tight_layout()

plt.savefig(
    "charts/top10_scores.png"
)

print("图表已保存到 charts/top10_scores.png")