import pandas as pd


def load_watchlist():
    df = pd.read_csv("data/watchlist.csv")
    return df["Ticker"].tolist()