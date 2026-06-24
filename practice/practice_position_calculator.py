ticker = input("股票代码：")

shares = int(
    input("持股数量：")
)

price = float(
    input("买入价格：")
)

position_value = (
    shares
    * price
)

print()

print(
    f"{ticker} "
    f"持仓市值 "
    f"{position_value:,.0f} 美元"
)