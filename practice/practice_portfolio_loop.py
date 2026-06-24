import pandas as pd

portfolio = pd.read_csv("../portfolio.csv")

print(portfolio)

portfolio["Position Value"] = (
    portfolio["Shares"]
    *
    portfolio["Cost"]
)

for _, row in portfolio.iterrows():
    print(
        f"{row['Ticker']} 持仓市值 {row['Position Value']:.0f} 美元"
    )

    print()

total_value = portfolio["Position Value"].sum()

print(f"组合总市值: {total_value:.0f} 美元")

portfolio["Weight %"] = (
    portfolio["Position Value"]
    /
    total_value
    *
    100
).round(2)

print()
print(portfolio)

print()
print("投资组合报告")
print("-" * 30)

for _, row in portfolio.iterrows():
    print(
        f"{row['Ticker']} "
        f"市值 {row['Position Value']:.0f} 美元 "
        f"占比 {row['Weight %']}%"
    )