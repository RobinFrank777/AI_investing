def say_hello():

    print("你好 Robin")
say_hello()

def show_stock():

    print("TSLA")
show_stock()

def show_stock(ticker):

    print(ticker)
show_stock("TSLA")
show_stock("NVDA")
show_stock("AMD")

def calculate_position_value(
    shares,
    price
):

    value = shares * price

    print(value)
calculate_position_value(
    2100,
    337.55
)

def calculate_position_value(
    shares,
    price
):

    return shares * price
value = calculate_position_value(
    2100,
    337.55
)

print(value)