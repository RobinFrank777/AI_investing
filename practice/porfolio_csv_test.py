import pandas as pd

portfolio_df = pd.read_csv("portfolio.csv")

print(portfolio_df)
print(portfolio_df.iloc[0])
print(portfolio_df.iloc[0]["Ticker"])
print(portfolio_df.iloc[0]["Shares"])
print(portfolio_df.iloc[0]["Cost"])