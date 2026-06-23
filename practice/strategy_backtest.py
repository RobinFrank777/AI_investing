from stock_loader import load_stock

ticker = "TSLA"

df = load_stock(ticker)

df["MA30"] = df["Close"].rolling(30).mean()
df["MA60"] = df["Close"].rolling(60).mean()

cash = 100000
shares = 0

buy_price = 0

wins = 0
losses = 0
best_trade = 0
worst_trade = 0

for i in range(60, len(df)):

    yesterday_ma30 = df["MA30"].iloc[i-1]
    yesterday_ma60 = df["MA60"].iloc[i-1]

    today_ma30 = df["MA30"].iloc[i]
    today_ma60 = df["MA60"].iloc[i]

    price = df["Close"].iloc[i]

    # 金叉买入

    if (
        yesterday_ma30 < yesterday_ma60
        and
        today_ma30 > today_ma60
    ):

        if shares == 0:

            shares = cash / price
            cash = 0
            buy_price = price

            print(
                f"BUY  {df['Date'].iloc[i]}  {price:.2f}"
            )

    # 死叉卖出

    elif (
        yesterday_ma30 > yesterday_ma60
        and
        today_ma30 < today_ma60
    ):

        if shares > 0:

            cash = shares * price

        trade_return = (
            price - buy_price
        ) / buy_price

        if trade_return > best_trade:
            best_trade = trade_return

        if trade_return < worst_trade:
            worst_trade = trade_return

        if price > buy_price:
            wins += 1
        else:
            losses += 1

        shares = 0

        print(
                f"SELL {df['Date'].iloc[i]} {price:.2f}"
            )

final_value = cash

if shares > 0:
    final_value = shares * df["Close"].iloc[-1]

print()
print(f"最终资产: {final_value:.2f}")
print(f"收益率: {(final_value/100000-1):.2%}")

total_trades = wins + losses

print(f"交易次数: {total_trades}")
print(f"盈利次数: {wins}")
print(f"亏损次数: {losses}")

if total_trades > 0:
    print(f"胜率: {wins / total_trades:.2%}")

    print(
    f"最大盈利交易: {best_trade:.2%}"
)

print(
    f"最大亏损交易: {worst_trade:.2%}"
)