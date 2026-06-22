import pandas as pd

from stock_loader import load_stock

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

table_html = '''
<table border="1" cellpadding="8">
<tr>
    <th>股票</th>
    <th>股数</th>
    <th>成本价</th>
    <th>现价</th>
    <th>市值</th>
    <th>总成本</th>
    <th>盈亏</th>
    <th>收益率</th>
</tr>
'''

for i in range(len(result_df)):

    row = result_df.iloc[i]

    profit = row["Profit"]

    if profit > 0:
        color = "green"
    else:
        color = "red"

    table_html += f'''
<tr>
    <td>{row["Ticker"]}</td>
    <td>{row["Shares"]}</td>
    <td>{row["Cost"]:.2f}</td>
    <td>{row["Current Price"]:.2f}</td>
    <td>{row["Market Value"]:.2f}</td>
    <td>{row["Cost Basis"]:.2f}</td>
    <td style="color:{color}">{row["Profit"]:.2f}</td>
    <td>{row["Profit Rate %"]:.2f}%</td>
</tr>
'''

table_html += '''
</table>
'''

html = f"""
<h1>投资组合报告</h1>

<p>总成本：{total_cost:.2f}</p>
<p>总市值：{total_value:.2f}</p>
<p>总盈亏：{total_profit:.2f}</p>
<p>总收益率：{total_profit_rate:.2%}</p>

<h2>收益率排行榜</h2>

{ranking_html}
<h2>持仓明细</h2>

{table_html}

<h2>资产配置图</h2>

<img src="charts/allocation.png" width="600">

"""

with open("report.html", "w") as f:
    f.write(html)

print("报告已生成")

