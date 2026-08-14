import pandas as pd
import numpy as np
import yfinance as yf

from config import DATA_DIR_PATH, display_path
from market_session import completed_daily_bars
from universe_source import load_active_universe


DATA_DIR = DATA_DIR_PATH
CANONICAL_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")
LAST_UPDATE_RESULTS = {}


def valid_canonical_ohlcv_rows(frame):
    """Return the unchanged, strict OHLCV validity mask used before writes."""
    dates = pd.to_datetime(frame["Date"], errors="coerce")
    numeric = frame.loc[:, CANONICAL_COLUMNS[1:]].apply(pd.to_numeric, errors="coerce")
    finite = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
    return pd.Series(finite, index=frame.index) & dates.notna() & (
        numeric[["Open", "High", "Low", "Close"]] > 0
    ).all(axis=1) & (numeric["Volume"] >= 0) & (
        numeric["High"] >= numeric[["Open", "Close", "Low"]].max(axis=1)
    ) & (
        numeric["Low"] <= numeric[["Open", "Close", "High"]].min(axis=1)
    )


def build_atomic_canonical_history(downloaded, existing=None):
    """Replace each valid refreshed date as one row; reject invalid rows."""
    fresh = downloaded.loc[:, list(CANONICAL_COLUMNS)].copy()
    fresh["Date"] = pd.to_datetime(fresh["Date"], errors="coerce")
    fresh = fresh.sort_values("Date", kind="mergesort").drop_duplicates(
        "Date", keep="last"
    )
    valid = valid_canonical_ohlcv_rows(fresh)
    rejected_dates = fresh.loc[~valid, "Date"].dropna().dt.strftime("%Y-%m-%d").tolist()
    safe_fresh = fresh.loc[valid].copy()

    frames = []
    if existing is not None and not existing.empty and set(CANONICAL_COLUMNS).issubset(existing.columns):
        prior = existing.loc[:, list(CANONICAL_COLUMNS)].copy()
        prior["Date"] = pd.to_datetime(prior["Date"], errors="coerce")
        prior = prior.loc[valid_canonical_ohlcv_rows(prior)].copy()
        frames.append(prior)
    frames.append(safe_fresh)
    canonical = pd.concat(frames, ignore_index=True)
    canonical = canonical.sort_values("Date", kind="mergesort").drop_duplicates(
        "Date", keep="last"
    ).reset_index(drop=True)
    canonical["Date"] = canonical["Date"].dt.strftime("%Y-%m-%d")
    return canonical.loc[:, list(CANONICAL_COLUMNS)], rejected_dates


def _atomic_write_csv(frame, path):
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def load_watchlist():
    """Return the managed market universe (kept for API compatibility)."""
    return load_active_universe()


def get_last_update_results():
    return dict(LAST_UPDATE_RESULTS)


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
        df = df[list(CANONICAL_COLUMNS)]

        existing = None
        if output_file.is_file():
            try:
                existing = pd.read_csv(output_file)
            except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError, OSError):
                existing = None
        df, rejected_dates = build_atomic_canonical_history(df, existing)
        if df.empty:
            raise ValueError("Downloaded data contains no valid canonical OHLCV row.")

        latest_date = pd.to_datetime(df["Date"], errors="raise").max().strftime("%Y-%m-%d")
        _atomic_write_csv(df, output_file)

        if rejected_dates:
            message = "Provider rows rejected by canonical OHLCV contract: " + ", ".join(rejected_dates)
            print(f"{ticker} 更新受限：{message}；保留最新有效日期 {latest_date}")
            return {
                "symbol": ticker,
                "status": "provider_rejected",
                "rows": len(df),
                "latest_date": latest_date,
                "output_path": output_path,
                "message": message,
                "rejected_dates": rejected_dates,
            }

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
    LAST_UPDATE_RESULTS.clear()
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
            LAST_UPDATE_RESULTS[ticker] = stock_result
            if stock_result is None or stock_result.get("status") == "success":
                result["succeeded"] += 1
            else:
                result["failed"] += 1
                result["failed_symbols"].append(ticker)
        except Exception as e:
            LAST_UPDATE_RESULTS[ticker] = {
                "symbol": ticker, "status": "failed", "message": str(e),
            }
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
