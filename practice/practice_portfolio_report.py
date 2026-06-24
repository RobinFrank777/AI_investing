def calculate_position_value(shares, price):
    return shares * price


def show_position(ticker, shares, price):

    value = calculate_position_value(
        shares,
        price
    )

    print(
        f"{ticker} "
        f"市值 {value:,.0f} 美元"
    )


show_position(
    "TSLA",
    2100,
    337.55
)

show_position(
    "NVDA",
    500,
    197.22
)

show_position(
    "AMD",
    150,
    461.82
)

tsla_value = calculate_position_value(
    2100,
    337.55
)

nvda_value = calculate_position_value(
    500,
    197.22
)

amd_value = calculate_position_value(
    150,
    461.82
)

total_value = (
    tsla_value
    + nvda_value
    + amd_value
)

print()
print("组合总市值")
print(f"{total_value:,.0f} 美元")

print()

if tsla_value > nvda_value:
    print("TSLA 大于 NVDA")

largest_value = max(
    tsla_value,
    nvda_value,
    amd_value
)

print()
print("最大持仓市值")
print(f"{largest_value:,.0f} 美元")