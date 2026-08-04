import pandas as pd
from config import WATCHLIST_INPUT_PATH


def load_watchlist():
    df = pd.read_csv(WATCHLIST_INPUT_PATH)
    return df["Ticker"].tolist()
