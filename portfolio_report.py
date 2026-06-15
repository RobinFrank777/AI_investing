import pandas as pd

def load_stock(ticker):
    file_path = f"data/{ticker}.csv"
    df = pd.read_csv(file_path, skiprows=1)
    df.columns = [
        "Date",
        "Close",
        "High",
        "Low",
        "Open",
        "Volume"
    ]
    return df

portfolio = {
    "TSLA": {
        "shares": 2100,
        "cost": 337.55
    },
    "GOOGL": {
        "shares": 350,
        "cost": 260.15
    },


    "AMD": {
        "shares": 150,
        "cost": 461.82
    },

    #没有它的csv数据
    #"TSM": {
    #    "shares": 150,
    #    "cost": 291.28
    #},
    "NVDA": {
        "shares": 500,
        "cost": 197.22
    },

    #没有它的csv数据
    #"RKLB": {
    #    "shares": 500,
    #   "cost": 18.44
    #},
    }
total_cost = 0

total_value = 0

total_profit = 0
for stock, info in portfolio.items():

    shares = info["shares"]

    cost = info["cost"]

    df = load_stock(stock)

    current_price = df.iloc[-1]["Close"]
    market_value = shares * current_price
    profit = market_value - (shares * cost)
    profit_rate = profit / (shares * cost) if shares * cost != 0 else 0
    total_cost += shares * cost
    total_value += market_value
    total_profit += profit
    print(f"股票：{stock}")

    print(f"持仓：{shares}")

    print(f"成本价：{cost}")

    print(f"现价：{current_price:.2f}")
    print(f"市值：{market_value:.2f}")

    print(f"盈亏：{profit:.2f}")

    print(f"收益率：{profit_rate:.2%}")
    print()
total_profit_rate = total_profit / total_cost

print("========组合汇总========")

print(f"总成本：{total_cost:.2f}")

print(f"总市值：{total_value:.2f}")

print(f"总盈亏：{total_profit:.2f}")

print(f"总收益率：{total_profit_rate:.2%}")