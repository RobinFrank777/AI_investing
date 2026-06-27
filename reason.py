def generate_reason(row):
    reasons = []

    if row["Close"] > row["MA20"]:
        reasons.append("Price above MA20")
    else:
        reasons.append("Price below MA20")

    if row["MA20"] > row["MA60"]:
        reasons.append("Bullish MA alignment")
    else:
        reasons.append("Bearish MA alignment")

    if row["Volume_Ratio"] > 1.5:
        reasons.append("Strong volume breakout")
    elif row["Volume_Ratio"] > 1.0:
        reasons.append("Above-average volume")
    else:
        reasons.append("Weak volume")

    if row["DistanceToHigh"] >= 0.9:
        reasons.append("Near 52-week high")
    else:
        reasons.append("Below 52-week high")

    if row["RSI14"] > 75:
        reasons.append("RSI overbought")
    elif row["RSI14"] < 60:
        reasons.append("RSI not overbought")
    else:
        reasons.append("Healthy RSI")

    return " | ".join(reasons)