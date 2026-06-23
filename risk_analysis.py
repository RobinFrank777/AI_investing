from stock_loader import load_stock

ticker = "TSLA"

df = load_stock(ticker)

prices = df["Close"]

peak = prices.iloc[0]

max_drawdown = 0

for price in prices:

    if price > peak:

        peak = price

    drawdown = (
        peak - price
    ) / peak

    if drawdown > max_drawdown:

        max_drawdown = drawdown

print(
    f"最大回撤: {max_drawdown:.2%}"
)