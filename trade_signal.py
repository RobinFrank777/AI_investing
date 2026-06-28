import pandas as pd

def generate_signals(rank_df):
    rank_df["TradeSignal"] = "IGNORE"

    rank_df.loc[
        rank_df["FinalScore"] >= 60,
        "TradeSignal"
    ] = "WATCH"

    rank_df.loc[
        (rank_df["FinalScore"] >= 75) &
        (rank_df["Volume_Ratio"] > 0.8) &
        (rank_df["DistanceToHigh"] >= 0.95) &
        (rank_df["Close"] > rank_df["MA20"]) &
        (rank_df["MA20"] > rank_df["MA60"]),
        "TradeSignal"
    ] = "BUY"

    return rank_df