def calculate_position_size(
    latest_atr,
    latest_rsi,
    account_size,
    risk_per_trade
):

    risk_dollar = account_size * risk_per_trade
    position_size = risk_dollar / (latest_atr * 2)
    if latest_rsi < 60:
        rsi_position_factor = 1.0
    elif latest_rsi < 75:
        rsi_position_factor = 0.8
    else:
        rsi_position_factor = 0.5

    position_size = position_size * rsi_position_factor
    return position_size, rsi_position_factor