import pandas as pd
import yfinance as yf
from pathlib import Path


DATA_DIR = Path("data")
WATCHLIST_FILE = DATA_DIR / "watchlist.csv"


def load_watchlist():
    df = pd.read_csv(WATCHLIST_FILE)
    return df["Ticker"].tolist()


def update_one_stock(ticker):
    print(f"正在更新 {ticker} ...")

    df = yf.download(
        ticker,
        period="2y",
        interval="1d",
        auto_adjust=False,
        progress=False
    )

    if df.empty:
        print(f"跳过 {ticker}，没有下载到数据")
        return

    # 处理多层列名
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # 日期在 index 里，先强制命名为 Date
    df.index.name = "Date"

    # 把 index 变成普通 Date 列
    df = df.reset_index()

    # 只保留我们需要的列
    required_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df = df[required_columns]

    output_file = DATA_DIR / f"{ticker}.csv"
    df.to_csv(output_file, index=False)

    latest_date = df["Date"].iloc[-1]
    print(f"{ticker} 已更新，最新日期：{latest_date}")


def update_all_stocks():
    tickers = load_watchlist()

    for ticker in tickers:
        try:
            update_one_stock(ticker)
        except Exception as e:
            print(f"更新 {ticker} 失败，原因：{e}")


if __name__ == "__main__":
    update_all_stocks()