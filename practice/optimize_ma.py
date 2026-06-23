from stock_loader import load_stock

ticker = "TSLA"

df = load_stock(ticker)

best_return = 0
best_short = 0
best_long = 0

for short_ma in [10, 20, 30, 40, 50]:

    for long_ma in [60, 80, 100, 120, 150]:

        if short_ma >= long_ma:
            continue

        temp_df = df.copy()

        temp_df["MA_S"] = (
            temp_df["Close"]
            .rolling(short_ma)
            .mean()
        )

        temp_df["MA_L"] = (
            temp_df["Close"]
            .rolling(long_ma)
            .mean()
        )

        cash = 100000
        shares = 0

        for i in range(long_ma, len(temp_df)):

            y_s = temp_df["MA_S"].iloc[i-1]
            y_l = temp_df["MA_L"].iloc[i-1]

            t_s = temp_df["MA_S"].iloc[i]
            t_l = temp_df["MA_L"].iloc[i]

            price = temp_df["Close"].iloc[i]

            if (
                y_s < y_l
                and
                t_s > t_l
            ):

                if shares == 0:
                    shares = cash / price
                    cash = 0

            elif (
                y_s > y_l
                and
                t_s < t_l
            ):

                if shares > 0:
                    cash = shares * price
                    shares = 0

        final_value = cash

        if shares > 0:
            final_value = (
                shares *
                temp_df["Close"].iloc[-1]
            )

        profit_rate = (
            final_value / 100000 - 1
        )

        print(
            f"MA{short_ma}/MA{long_ma} "
            f"{profit_rate:.2%}"
        )

        if profit_rate > best_return:

            best_return = profit_rate
            best_short = short_ma
            best_long = long_ma

print()
print("======最佳参数======")

print(
    f"MA{best_short}/MA{best_long}"
)

print(
    f"收益率: {best_return:.2%}"
)