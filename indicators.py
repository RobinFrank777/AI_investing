import pandas as pd


def calculate_indicators(df):

    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()
    df["High60"] = (
        df["Close"]
        .shift(1)
        .rolling(window=60)
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
    
    return df