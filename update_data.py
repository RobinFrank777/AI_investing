import pandas as pd
import yfinance as yf

from config import DATA_DIR_PATH
from universe_manager import load_universe


DATA_DIR = DATA_DIR_PATH


def load_watchlist():
    """Return the managed market universe (kept for API compatibility)."""
    return load_universe()


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
    try:
        symbols = load_universe()
    except (FileNotFoundError, ValueError) as error:
        print(f"Unable to load market universe: {error}")
        raise

    result = {
        "total": len(symbols),
        "succeeded": 0,
        "failed": 0,
        "failed_symbols": [],
    }

    if not symbols:
        print("No enabled symbols found in market universe.")
        return result

    for ticker in symbols:
        try:
            update_one_stock(ticker)
            result["succeeded"] += 1
        except Exception as e:
            result["failed"] += 1
            result["failed_symbols"].append(ticker)
            print(f"更新 {ticker} 失败，原因：{e}")

    return result


def main():
    try:
        update_all_stocks()
    except (FileNotFoundError, ValueError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
