from stock_loader import load_stock

import pandas as pd


tickers = ["TSLA", "NVDA", "AMD", "GOOGL"]

results = []


for ticker in tickers:

    df = load_stock(ticker)

    returns = df["Close"].pct_change()

    avg_daily_return = returns.mean()

    daily_volatility = returns.std()

    annual_return = avg_daily_return * 252

    annual_volatility = daily_volatility * (252 ** 0.5)

    sharpe = annual_return / annual_volatility

    prices = df["Close"]

    peak = prices.iloc[0]

    max_drawdown = 0

    for price in prices:

        if price > peak:
            peak = price

        drawdown = (peak - price) / peak

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    results.append({
        "Ticker": ticker,
        "Annual Return %": annual_return * 100,
        "Annual Volatility %": annual_volatility * 100,
        "Max Drawdown %": max_drawdown * 100,
        "Sharpe": sharpe
    })


result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    by="Sharpe",
    ascending=False
)

print(result_df)

result_df.to_csv(
    "stock_personality.csv",
    index=False
)

print(
    "stock_personality.csv 已生成"
)