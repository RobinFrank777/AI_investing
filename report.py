from datetime import datetime
from config import STOCK_RANK_OUTPUT


def save_daily_report(rank_df):
    now = datetime.now()

    report_date = now.strftime("%Y-%m-%d")
    report_generated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    report_path = (
        f"reports/daily_trading_report_{report_date}.txt"
    )

    buy_df = rank_df[rank_df["TradeSignal"] == "BUY"]
    watch_df = rank_df[rank_df["TradeSignal"] == "WATCH"]
    top10_df = rank_df.head(10)
    market_data_dates = sorted(
    rank_df["MarketDataDate"]
    .dropna()
    .astype(str)
    .unique()
    )

    if len(market_data_dates) == 1:
        market_data_date = market_data_dates[0]
    elif len(market_data_dates) == 0:
        market_data_date = "Unavailable"
    else:
        market_data_date = ", ".join(market_data_dates)

    with open(report_path, "w", encoding="utf-8") as f:
        buy_count = len(buy_df)
        watch_count = len(watch_df)
        ignore_count = len(rank_df[rank_df["TradeSignal"] == "IGNORE"])

        avg_score = rank_df["FinalScore"].mean()
        avg_conf = rank_df["Confidence"].mean()

        top_pick = rank_df.iloc[0]["Ticker"]

        f.write("=" * 60 + "\n")
        f.write("DAILY TRADING REPORT\n")
        f.write("=" * 60 + "\n\n")

        f.write(
            f"{'Report Generated At':<22}: "
            f"{report_generated_at}\n"
        )

        f.write(
            f"{'Market Data Date':<22}: "
            f"{market_data_date}\n"
        )

        f.write(
            f"{'Source File':<22}: "
            f"{STOCK_RANK_OUTPUT}\n\n"
        )

        f.write("=" * 60 + "\n")
        f.write("MARKET OVERVIEW\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"BUY Signals        : {buy_count}\n")
        f.write(f"WATCH Signals      : {watch_count}\n")
        f.write(f"IGNORE Signals     : {ignore_count}\n\n")

        f.write(f"Average Score      : {avg_score:.2f}\n")
        f.write(f"Average Confidence : {avg_conf:.1f}\n\n")

        f.write(f"Top Candidate      : {top_pick}\n\n")

        f.write("=" * 60 + "\n")
        f.write("TOP 10 STOCK RANKING\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"{'Ticker':<8}{'Score':<10}{'Signal':<10}{'Confidence':<12}\n")
        f.write("-" * 42 + "\n")

        for _, row in top10_df.iterrows():
            f.write(
                f"{row['Ticker']:<8}"
                f"{row['FinalScore']:<10.2f}"
                f"{row['TradeSignal']:<10}"
                f"{row['Confidence']:<12}\n"
            )

        f.write("\n" + "=" * 60 + "\n")
        f.write("TODAY'S BUY LIST\n")
        f.write("=" * 60 + "\n\n")

        if buy_df.empty:
            f.write("No BUY signals today.\n")
        else:
            for _, row in buy_df.iterrows():
                f.write(f"\nTicker: {row['Ticker']}\n")
                f.write(f"Price: {row['Close']:.2f}\n")
                f.write(f"Final Score: {row['FinalScore']:.2f}\n")
                f.write(f"Confidence: {row['Confidence']} / 100\n")
                f.write(f"Position Size: {row['PositionSize']} shares\n")
                f.write(f"Stop Loss: {row['StopLoss']:.2f}\n")
                f.write("Reasons:\n")
                for reason in row["Reason"].split(" | "):
                    f.write(f"  - {reason}\n")

        f.write("\n" + "=" * 60 + "\n")
        f.write("TODAY'S WATCH LIST\n")
        f.write("=" * 60 + "\n\n")

        if watch_df.empty:
            f.write("No WATCH signals today.\n")
        else:
            for _, row in watch_df.iterrows():
                f.write(f"\nTicker: {row['Ticker']}\n")
                f.write(f"Price: {row['Close']:.2f}\n")
                f.write(f"Final Score: {row['FinalScore']:.2f}\n")
                f.write(f"Confidence: {row['Confidence']} / 100\n")
                f.write(f"Distance High: {row['DistanceToHigh']:.1%}\n")
                f.write(f"Volume Ratio: {row['Volume_Ratio']:.2f}x\n")
                f.write(f"RSI(14): {row['RSI14']:.1f}\n")
                f.write("Reasons:\n")
                for reason in row["Reason"].split(" | "):
                    f.write(f"  - {reason}\n")

    print(f"\nDaily report saved to {report_path}")