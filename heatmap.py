import matplotlib.pyplot as plt

import pandas as pd

df = pd.read_csv("results/ma_optimization.csv")

print(df.head())

pivot = df.pivot(
    index="Short MA",
    columns="Long MA",
    values="Return %"
)

print(pivot)

plt.figure(figsize=(8,6))

plt.imshow(pivot)

plt.colorbar(label="Return %")

plt.xticks(
    range(len(pivot.columns)),
    pivot.columns
)

plt.yticks(
    range(len(pivot.index)),
    pivot.index
)

plt.xlabel("Long MA")
plt.ylabel("Short MA")

plt.title("Moving Average Optimization")

for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):

        value = pivot.iloc[i, j]

        plt.text(
            j,
            i,
            f"{value:.0f}",
            ha="center",
            va="center",
            color="white"
        )


plt.savefig(
    "charts/heatmap.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()