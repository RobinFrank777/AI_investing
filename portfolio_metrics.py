import pandas as pd

portfolio = pd.read_csv("portfolio.csv")

print(portfolio)

print()

print(portfolio["Shares"])

print()

print(portfolio["Cost"])

print()

print(
    portfolio["Shares"]
    *
    portfolio["Cost"]
)

position_value = (
    portfolio["Shares"]
    *
    portfolio["Cost"]
)

print()
print(position_value)

print()

total_cost = position_value.sum()

print("组合总成本：")
print(total_cost)

print()

weight = position_value / total_cost

print("仓位权重：")
print(weight)

portfolio["Weight"] = weight

portfolio["Weight %"] = (
    portfolio["Weight"]
    * 100
).round(2)

print()
print(portfolio)

print()

sorted_portfolio = portfolio.sort_values(
    by="Weight %",
    ascending=False
).reset_index(drop=True)

print("按仓位从大到小排序：")
print(sorted_portfolio)

print()

print("最大仓位：")
print(portfolio["Weight %"].max())

print()

print("最小仓位：")
print(portfolio["Weight %"].min())

print()

largest_position = portfolio[
    portfolio["Weight %"] == portfolio["Weight %"].max()
]

print(largest_position)

smallest_position = portfolio[
    portfolio["Weight %"] == portfolio["Weight %"].min()
]

print(smallest_position)

print()

large_positions = portfolio[
    portfolio["Weight %"] > 10
]

print("仓位超过10%的股票：")
print(large_positions)

print()

selected_stocks = portfolio[
    (portfolio["Cost"] > 200)
    &
    (portfolio["Shares"] > 300)
]

print("满足双条件的股票：")
print(selected_stocks)

print()

selected_stocks = portfolio[
    (portfolio["Cost"] > 400)
    |
    (portfolio["Shares"] > 1000)
]

print("满足任意一个条件的股票：")
print(selected_stocks)

print(
    large_positions[
        ["Ticker", "Weight %"]
    ]
)

top2 = sorted_portfolio.head(2)

print()
print("前两大持仓：")
print(top2)

last2 = sorted_portfolio.tail(2)

print()
print("后两大持仓：")
print(last2)

print()

print("第一名股票：")
print(sorted_portfolio.iloc[0])

print()

print("第二名股票：")
print(sorted_portfolio.iloc[1])

largest_stock = sorted_portfolio.iloc[0]

print()
print("股票代码：")
print(largest_stock["Ticker"])

print()
print("仓位比例：")
print(largest_stock["Weight %"])

print()

print(
    f"最大持仓是 {largest_stock['Ticker']}，占组合 {largest_stock['Weight %']}%"
)