import pandas as pd

def load_stock(ticker):
    file_path = f"data/{ticker}.csv"
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

df = load_stock("NVDA")
print(df.iloc[-1]["Close"])