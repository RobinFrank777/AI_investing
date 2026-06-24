import yfinance as yf
import pandas as pd
from pathlib import Path

# 你要抓取的股票代码
watchlist_df = pd.read_csv("data/watchlist.csv")
tickers = watchlist_df["Ticker"].tolist()

# 数据时间范围
start_date = "2024-01-01"
end_date = "2026-05-25"

# 保存目录
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

for ticker in tickers:
    print(f"正在抓取 {ticker} ...")

    df = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        print(f"{ticker} 没有抓到数据")
        continue

    file_path = data_dir / f"{ticker}.csv"
    df.to_csv(file_path)

    print(f"{ticker} 已保存到 {file_path}")

print("全部完成")
