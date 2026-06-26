import pandas as pd


def calculate_indicators(df):

    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()

    df["High60"] = (
        df["Close"]
        .shift(1)
        .rolling(window=60)
        .max()
    )
    df["High252"] = (
        df["Close"]
        .shift(1)
        .rolling(window=252)
        .max()
    )

    df["VolumeMA20"] = df["Volume"].rolling(window=20).mean()

    df["PrevClose"] = df["Close"].shift(1)

    df["TR"] = (
        pd.concat(
            [
                df["High"] - df["Low"],
                (df["High"] - df["PrevClose"]).abs(),
                (df["Low"] - df["PrevClose"]).abs()
            ],
            axis=1
        )
    ).max(axis=1)

    df["ATR14"] = (
        df["TR"]
        .rolling(window=14)
        .mean()
    )

    delta = df["Close"].diff()

    gain = delta.where(delta > 0, 0)

    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=14).mean()

    avg_loss = loss.rolling(window=14).mean()

    rs = avg_gain / avg_loss

    df["RSI14"] = 100 - (
        100 / (1 + rs)
    )

    return df