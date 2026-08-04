import pandas as pd
from config import DATA_DIR_PATH


def load_stock(ticker):
    file_path = DATA_DIR_PATH / f"{ticker}.csv"
    df = pd.read_csv(file_path, skiprows=1)
    df.columns = [
        "Date",
        "Close",
        "High",
        "Low",
        "Open",
        "Volume"
    ]
    return df
