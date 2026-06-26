import pandas as pd

def calculate_rank_score(
    latest_close,
    latest_ma20,
    latest_ma60,
    recent_return,
    return_60d,
    volume_ratio,
    latest_high60,
    distance_to_high,
    latest_macd,
    latest_signal,
    latest_hist
):
    trend_score = 0
    momentum_score = 0
    volume_score = 0
    risk_score = 0
    confidence = 0

    # Trend Score
    if latest_close > latest_ma20:
        trend_score += 30
        confidence += 20

    if latest_ma20 > latest_ma60:
        trend_score += 30
        confidence += 20

    if latest_close > latest_high60:
        trend_score += 20

    if distance_to_high >= 0.95:
        trend_score += 30
        confidence += 20
    elif distance_to_high >= 0.90:
        trend_score += 20
        confidence += 10
    elif distance_to_high >= 0.80:
        trend_score += 10
        confidence += 5

    # Momentum Score
    momentum_score += recent_return * 70
    momentum_score += return_60d * 30
    if latest_macd > latest_signal:
        momentum_score += 20
        confidence += 15

    if latest_macd > 0:
        momentum_score += 10
        

    if latest_hist > 0:
        momentum_score += 10
        confidence += 10

    # Volume Score
    if volume_ratio > 1.5:
        volume_score += 20
    elif volume_ratio > 1.0:
        volume_score += 10
        confidence += 8

    # Risk Score
    risk_score += 50

    score = (
        trend_score * 0.40
        + momentum_score * 0.25
        + volume_score * 0.20
        + risk_score * 0.15
    )

    return score, confidence

def calculate_final_score(rank_df):
    rank_df["RS_Score"] = (
    rank_df["60Day_Return"]
    .rank(pct=True)
    * 100
    )
    rank_df["NearHighScore"] = 0

    rank_df.loc[
        rank_df["DistanceToHigh"] >= 1.00,
        "NearHighScore"
    ] = 40

    rank_df.loc[
        (rank_df["DistanceToHigh"] >= 0.98) &
        (rank_df["DistanceToHigh"] < 1.00),
        "NearHighScore"
    ] = 30

    rank_df.loc[
        (rank_df["DistanceToHigh"] >= 0.95) &
        (rank_df["DistanceToHigh"] < 0.98),
        "NearHighScore"
    ] = 20

    rank_df.loc[
        (rank_df["DistanceToHigh"] >= 0.90) &
        (rank_df["DistanceToHigh"] < 0.95),
        "NearHighScore"
    ] = 10

    rank_df["FinalScore"] = (
        rank_df["Score"] * 0.7
        + rank_df["RS_Score"] * 0.2
        + rank_df["NearHighScore"] * 0.1
    )
    return rank_df