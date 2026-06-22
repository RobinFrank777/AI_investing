from stock_loader import load_stock

ticker = "TSLA"

df = load_stock(ticker)

cash = 100000
shares = 0

print(f"初始资金: {cash}")

for i in range(len(df)):

    price = df["Close"].iloc[i]

    if shares == 0:
        shares = cash / price
        cash = 0

    final_value = shares * price

print(f"最终资产: {final_value:.2f}")

profit = final_value - 100000

print(f"总盈利: {profit:.2f}")

profit_rate = profit / 100000

print(f"收益率: {profit_rate:.2%}")