import pandas as pd
import yfinance as yf

from config import DATA_DIR_PATH, display_path
from market_session import completed_daily_bars
from universe_source import load_active_universe


DATA_DIR = DATA_DIR_PATH


def load_watchlist():
    """Return the managed market universe (kept for API compatibility)."""
    return load_active_universe()


def update_one_stock(ticker):
    """Download one symbol and return a stable result dictionary."""
    print(f"正在更新 {ticker} ...")
    output_file = DATA_DIR / f"{ticker}.csv"
    output_path = display_path(output_file)

    try:
        df = yf.download(
            ticker,
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df.empty:
            print(f"跳过 {ticker}，没有下载到数据")
            return {
                "symbol": ticker,
                "status": "empty",
                "rows": 0,
                "latest_date": None,
                "output_path": output_path,
                "message": "No data returned by Yahoo Finance.",
            }

        # 处理多层列名
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df = completed_daily_bars(df)
        if df.empty:
            raise ValueError("Downloaded data contains no completed daily session.")

        # 日期在 index 里，先强制命名为 Date
        df.index.name = "Date"

        # 把 index 变成普通 Date 列
        df = df.reset_index()

        # 只保留我们需要的列
        required_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df = df[required_columns]

        parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
        parsed_close = pd.to_numeric(df["Close"], errors="coerce")
        valid_rows = parsed_dates.notna() & parsed_close.notna()
        if not valid_rows.any():
            raise ValueError("Downloaded data contains no valid Date and Close row.")

        latest_date = parsed_dates[valid_rows].max().strftime("%Y-%m-%d")
        df.to_csv(output_file, index=False)

        print(f"{ticker} 已更新，最新日期：{latest_date}")
        return {
            "symbol": ticker,
            "status": "success",
            "rows": len(df),
            "latest_date": latest_date,
            "output_path": output_path,
            "message": "",
        }
    except Exception as error:
        message = str(error)
        print(f"更新 {ticker} 失败，原因：{message}")
        return {
            "symbol": ticker,
            "status": "failed",
            "rows": 0,
            "latest_date": None,
            "output_path": output_path,
            "message": message,
        }


def update_all_stocks():
    try:
        symbols = load_active_universe()
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
            stock_result = update_one_stock(ticker)
            if stock_result is None or stock_result.get("status") == "success":
                result["succeeded"] += 1
            else:
                result["failed"] += 1
                result["failed_symbols"].append(ticker)
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
