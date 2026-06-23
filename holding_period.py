from stock_loader import load_stock

ticker = "TSLA"

df = load_stock(ticker)

for hold_days in [5,10,20,30,60,90]:

    profits = []

    for i in range(len(df)-hold_days):

        buy_price = df["Close"].iloc[i]

        sell_price = df["Close"].iloc[i+hold_days]

        profit = (
            sell_price
            /
            buy_price
            -
            1
        )

        profits.append(profit)

    avg_profit = sum(profits) / len(profits)

    print(
        f"持有{hold_days}天 "
        f"{avg_profit:.2%}"
    )