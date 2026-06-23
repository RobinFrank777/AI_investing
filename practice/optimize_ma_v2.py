import pandas as pd

from stock_loader import load_stock


ticker = "TSLA"

df = load_stock(ticker)

results = []

best_return = -999
best_short = 0
best_long = 0


for short_ma in [10, 20, 30, 40, 50]:

    for long_ma in [60, 80, 100, 120, 150]:

        temp_df = df.copy()

        temp_df["MA_Short"] = temp_df["Close"].rolling(short_ma).mean()
        temp_df["MA_Long"] = temp_df["Close"].rolling(long_ma).mean()

        cash = 100000
        shares = 0

        for i in range(long_ma, len(temp_df)):

            yesterday_short = temp_df["MA_Short"].iloc[i - 1]
            yesterday_long = temp_df["MA_Long"].iloc[i - 1]

            today_short = temp_df["MA_Short"].iloc[i]
            today_long = temp_df["MA_Long"].iloc[i]

            price = temp_df["Close"].iloc[i]

            if (
                yesterday_short < yesterday_long
                and
                today_short > today_long
            ):
                if shares == 0:
                    shares = cash / price
                    cash = 0

            elif (
                yesterday_short > yesterday_long
                and
                today_short < today_long
            ):
                if shares > 0:
                    cash = shares * price
                    shares = 0

        final_value = cash

        if shares > 0:
            final_value = shares * temp_df["Close"].iloc[-1]

        profit_rate = final_value / 100000 - 1

        results.append({
            "Short MA": short_ma,
            "Long MA": long_ma,
            "Return %": profit_rate * 100
        })

        if profit_rate > best_return:
            best_return = profit_rate
            best_short = short_ma
            best_long = long_ma


result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    "Return %",
    ascending=False
)

print("======TOP10======")
print(result_df.head(10))

print()
print("======最佳参数======")
print(f"MA{best_short}/MA{best_long}")
print(f"收益率: {best_return:.2%}")

result_df.to_csv(
    "ma_optimization.csv",
    index=False
)

print()
print("ma_optimization.csv 已生成")