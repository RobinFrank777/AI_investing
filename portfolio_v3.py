import pandas as pd

from stock_loader import load_stock

portfolio_df = pd.read_csv("portfolio.csv")

portfolio_df = pd.read_csv("portfolio.csv")

total_cost = 0

total_value = 0

total_profit = 0

results = []

for i in range(len(portfolio_df)):

    ticker = portfolio_df.iloc[i]["Ticker"]

    shares = portfolio_df.iloc[i]["Shares"]

    cost = portfolio_df.iloc[i]["Cost"]

    df = load_stock(ticker)

    current_price = df.iloc[-1]["Close"]

    print("股票：",ticker)

    print("股数：",shares)

    print("成本：",cost)

    print("当前价格：",f"{current_price:.2f}")

    market_value = shares * current_price
    cost_basis = shares * cost
    profit = market_value - cost_basis
    profit_rate = profit / cost_basis

    results.append({
    "Ticker": ticker,
    "Shares": shares,
    "Cost": cost,
    "Current Price": current_price,
    "Market Value": market_value,
    "Cost Basis": cost_basis,
    "Profit": profit,
    "Profit Rate": profit_rate
    })

    total_cost += cost_basis
    total_value += market_value
    total_profit += profit

    print("市值:", f"{market_value:.2f}")
    print("总成本:", f"{cost_basis:.2f}")
    print("盈亏:", f"{profit:.2f}")
    print("盈亏率:", f"{profit_rate:.2%}")
    print()
result_df = pd.DataFrame(results)
result_df = result_df.sort_values(by="Profit Rate", ascending=False)
result_df["Profit Rate %"] = (
    result_df["Profit Rate"] * 100
).round(2)
result_df.to_csv(
    "ranking.csv",
    index=False
)

total_profit_rate = total_profit / total_cost

print("========组合汇总========")

print(f"总成本: {total_cost:.2f}")

print(f"总市值: {total_value:.2f}")

print(f"总盈亏: {total_profit:.2f}")

print(f"总收益率: {total_profit_rate:.2%}")

print("========收益率排行榜========")

for i in range(len(result_df)):

    row = result_df.iloc[i]

    print(f"{row['Ticker']}: {row['Profit Rate']:.2%}")


ranking_html = ""

for i in range(len(result_df)):
    row = result_df.iloc[i]
    ranking_html += f"<p>{i+1}. {row['Ticker']} {row['Profit Rate %']}%</p>"

html = f"""
<h1>投资组合报告</h1>

<p>总成本：{total_cost:.2f}</p>
<p>总市值：{total_value:.2f}</p>
<p>总盈亏：{total_profit:.2f}</p>
<p>总收益率：{total_profit_rate:.2%}</p>

<h2>收益率排行榜</h2>

{ranking_html}
"""

with open("report.html", "w") as f:
    f.write(html)

print("报告已生成")