import pandas as pd

portfolio = pd.read_csv("../portfolio.csv")

portfolio["Position Value"] = (
    portfolio["Shares"]
    * portfolio["Cost"]
)

total_value = portfolio["Position Value"].sum()

portfolio["Weight %"] = (
    portfolio["Position Value"]
    / total_value
    * 100
).round(2)

for _, row in portfolio.iterrows():

    if row["Weight %"] > 20:

        risk = "高风险"

    elif row["Weight %"] > 10:

        risk = "中等仓位"

    else:

        risk = "小仓位"

    print(
        f"{row['Ticker']} "
        f"占比 {row['Weight %']}% "
        f"{risk}"
    )