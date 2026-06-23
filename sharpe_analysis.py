from stock_loader import load_stock

import pandas as pd

ticker = "TSLA"

df = load_stock(ticker)

returns = df["Close"].pct_change()

avg_return = returns.mean()

std_return = returns.std()

sharpe = (
    avg_return
    /
    std_return
) * (252 ** 0.5)

print(
    f"平均日收益: {avg_return:.4%}"
)

print(
    f"波动率: {std_return:.4%}"
)

print(
    f"夏普比率: {sharpe:.2f}"
)