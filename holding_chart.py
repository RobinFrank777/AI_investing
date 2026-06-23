from stock_loader import load_stock

import matplotlib.pyplot as plt

ticker = "TSLA"

df = load_stock(ticker)

days_list = [5,10,20,30,60,90]

profits = []

for hold_days in days_list:

    temp = []

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

        temp.append(profit)

    avg_profit = sum(temp) / len(temp)

    profits.append(avg_profit * 100)

plt.figure(figsize=(8,5))

plt.plot(
    days_list,
    profits,
    marker="o"
)

plt.title("Holding Period Analysis")

plt.xlabel("Days Held")

plt.ylabel("Average Return %")

plt.grid()

plt.show()