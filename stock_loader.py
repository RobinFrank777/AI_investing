import numpy as np
import pandas as pd
from config import DATA_DIR_PATH


REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
PRICE_COLUMNS = ["Open", "High", "Low", "Close"]
NUMERIC_COLUMNS = [*PRICE_COLUMNS, "Volume"]


def load_stock_file(file_path, *, ticker=None):
    label = ticker or str(file_path)
    df = pd.read_csv(file_path)

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Stock data for {label} is missing required columns: {missing_columns}"
        )

    df = df.loc[:, REQUIRED_COLUMNS].copy()
    if df.empty:
        raise ValueError(f"Stock data for {label} contains no rows")

    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError(f"Stock data for {label} contains invalid dates")
    if parsed_dates.duplicated().any():
        raise ValueError(f"Stock data for {label} contains duplicate dates")
    if not parsed_dates.is_monotonic_increasing:
        raise ValueError(f"Stock data for {label} dates must be increasing")

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if not np.isfinite(df[NUMERIC_COLUMNS].to_numpy(dtype=float)).all():
        raise ValueError(f"Stock data for {label} contains invalid numeric values")

    if (df[PRICE_COLUMNS] <= 0).any().any():
        raise ValueError(f"Stock data for {label} contains non-positive prices")
    if (df["Volume"] < 0).any():
        raise ValueError(f"Stock data for {label} contains negative volume")
    if (
        (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
        | (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
    ).any():
        raise ValueError(f"Stock data for {label} violates OHLC price relationships")

    return df


def load_stock(ticker):
    file_path = DATA_DIR_PATH / f"{ticker}.csv"
    return load_stock_file(file_path, ticker=ticker)
