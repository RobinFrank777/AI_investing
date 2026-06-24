def calculate_position_value(
    shares,
    price
):
    return shares * price

def show_position(
    ticker,
    shares,
    price
):

    value = calculate_position_value(
        shares,
        price
    )

    print(
        f"{ticker} "
        f"市值 "
        f"{value:,.0f}"
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