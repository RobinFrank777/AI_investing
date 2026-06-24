def analyze_stock(
    stock,
    shares,
    price
):

    value = shares * price

    print(
        f"{stock} "
        f"市值 {value:,.0f} 美元"
    )

analyze_stock(
    "TSLA",
    2100,
    337.55
)

analyze_stock(
    "NVDA",
    500,
    197.22
)

analyze_stock(
    "AMD",
    150,
    461.82
)

portfolio = [

    ["TSLA", 2100, 337.55],

    ["NVDA", 500, 197.22],

    ["AMD", 150, 461.82]

]

print(portfolio)

for item in portfolio:
    print(item)

for item in portfolio:

    print(item[0])

for item in portfolio:

    ticker = item[0]

    shares = item[1]

    price = item[2]

    print(
        ticker,
        shares,
        price
    )

for item in portfolio:

    ticker = item[0]

    shares = item[1]

    price = item[2]

    value = shares * price

    print(
        f"{ticker} 市值 {value:,.0f} 美元"
    )

total_value = 0

for item in portfolio:

    shares = item[1]

    price = item[2]

    value = shares * price

    total_value = total_value + value

print()
print("组合总市值")
print(f"{total_value:,.0f} 美元")