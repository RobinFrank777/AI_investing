"""Diagnostic-only historical sensitivity analysis for production FinalScore."""

from pathlib import Path

import pandas as pd

from indicators import calculate_indicators
from score import (
    SCORE_MODEL_VERSION,
    calculate_final_score,
    calculate_rank_score_diagnostics,
)
from stock_loader import load_stock
from watchlist import load_watchlist


THRESHOLDS = (50, 55, 60, 65, 70, 75, 80, 85, 90)
OUTPUT_PATH = Path(__file__).resolve().parent / "results" / "score_threshold_analysis.csv"
IMPACT_OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "score_model_v3.8.1_r1_impact.csv"
)
OUTPUT_COLUMNS = (
    "Threshold",
    "SignalCount",
    "EligibleObservationCount",
    "UniversePercentage",
    "Average5DForwardReturn",
    "Average20DForwardReturn",
    "Average60DForwardReturn",
    "WinRate20D",
    "MaximumDrawdown20D",
    "Volatility20D",
)


def build_ticker_score_inputs(ticker, data=None):
    """Build date-local inputs using the canonical loader and current indicators."""
    source = load_stock(ticker) if data is None else data.copy(deep=True)
    frame = calculate_indicators(source).copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="raise")
    frame["Ticker"] = ticker
    frame["Volume_Ratio"] = frame["Volume"] / frame["VolumeMA20"]
    frame["DistanceToHigh"] = frame["Close"] / frame["High252"]
    frame["20Day_Return"] = frame["Close"] / frame["Close"].shift(19) - 1
    frame["60Day_Return"] = frame["Close"] / frame["Close"].shift(59) - 1
    for horizon in (5, 20, 60):
        frame[f"Forward{horizon}DReturn"] = (
            frame["Close"].shift(-horizon) / frame["Close"] - 1
        )
    required = (
        "MA20", "MA60", "High60", "DistanceToHigh", "Volume_Ratio",
        "MACD", "MACD_Signal", "Histogram", "20Day_Return", "60Day_Return",
    )
    return frame.dropna(subset=list(required)).reset_index(drop=True)


def build_historical_score_table(tickers=None, market_data=None):
    """Reconstruct the current production score for each eligible date/symbol."""
    symbols = load_watchlist() if tickers is None else list(tickers)
    rows = []
    for ticker in symbols:
        data = None if market_data is None else market_data[ticker]
        frame = build_ticker_score_inputs(ticker, data=data)
        for _, source in frame.iterrows():
            components = calculate_rank_score_diagnostics(
                source["Close"],
                source["MA20"],
                source["MA60"],
                source["20Day_Return"],
                source["60Day_Return"],
                source["Volume_Ratio"],
                source["High60"],
                source["DistanceToHigh"],
                source["MACD"],
                source["MACD_Signal"],
                source["Histogram"],
            )
            rows.append(
                {
                    "Ticker": ticker,
                    "Date": source["Date"],
                    "ScoreModelVersion": SCORE_MODEL_VERSION,
                    "Score": components["RawScore"],
                    "TrendScore": components["TrendScore"],
                    "MomentumScore": components["MomentumScore"],
                    "60Day_Return": source["60Day_Return"],
                    "DistanceToHigh": source["DistanceToHigh"],
                    "Close": source["Close"],
                    "MA20": source["MA20"],
                    "MA60": source["MA60"],
                    "Volume_Ratio": source["Volume_Ratio"],
                    "Forward5DReturn": source["Forward5DReturn"],
                    "Forward20DReturn": source["Forward20DReturn"],
                    "Forward60DReturn": source["Forward60DReturn"],
                    "MACDContribution": components["MACDContribution"],
                    "ReturnMomentumContribution": components[
                        "ReturnMomentumContribution"
                    ],
                    "VolumeScore": components["VolumeScore"],
                    "RiskScore": components["RiskScore"],
                }
            )
    scores = pd.DataFrame(rows)
    if scores.empty:
        return scores
    scored_dates = []
    for _, group in scores.groupby("Date", sort=True):
        scored_dates.append(calculate_final_score(group.copy()))
    return pd.concat(scored_dates, ignore_index=True).sort_values(
        ["Date", "Ticker"], kind="mergesort"
    ).reset_index(drop=True)


def _maximum_drawdown_from_daily_cohorts(signals):
    valid = signals.dropna(subset=["Forward20DReturn"])
    if valid.empty:
        return float("nan")
    cohort_20d = valid.groupby("Date")["Forward20DReturn"].mean().sort_index()
    daily_equivalent = (1 + cohort_20d).pow(1 / 20) - 1
    equity = (1 + daily_equivalent).cumprod()
    return float((equity / equity.cummax() - 1).min())


def analyze_thresholds(scores, thresholds=THRESHOLDS):
    """Summarize threshold-only signal observations without optimizing a cutoff."""
    if scores.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    rows = []
    total = len(scores)
    for threshold in thresholds:
        signals = scores.loc[scores["FinalScore"] >= threshold]
        forward20 = signals["Forward20DReturn"].dropna()
        rows.append(
            {
                "Threshold": threshold,
                "SignalCount": len(signals),
                "EligibleObservationCount": total,
                "UniversePercentage": len(signals) / total,
                "Average5DForwardReturn": signals["Forward5DReturn"].mean(),
                "Average20DForwardReturn": forward20.mean(),
                "Average60DForwardReturn": signals["Forward60DReturn"].mean(),
                "WinRate20D": (forward20 > 0).mean(),
                "MaximumDrawdown20D": _maximum_drawdown_from_daily_cohorts(signals),
                "Volatility20D": forward20.std(ddof=1),
            }
        )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def run_threshold_analysis(output_path=OUTPUT_PATH):
    scores = build_historical_score_table()
    analysis = analyze_thresholds(scores)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    analysis.to_csv(path, index=False)
    return analysis


def build_score_model_impact(scores):
    """Compare the retired constant-RiskScore model with the active model."""
    impact = scores.loc[
        :,
        ["Ticker", "Date", "ScoreModelVersion", "FinalScore"],
    ].copy()
    impact = impact.rename(columns={"FinalScore": "NewFinalScore"})
    impact["OldFinalScore"] = impact["NewFinalScore"] + 5.25
    impact["FinalScoreShift"] = (
        impact["NewFinalScore"] - impact["OldFinalScore"]
    )
    impact["OldThresholdBand"] = pd.cut(
        impact["OldFinalScore"],
        bins=[float("-inf"), 60, 75, float("inf")],
        labels=["IGNORE", "WATCH", "BUY"],
        right=False,
    ).astype(str)
    impact["NewThresholdBand"] = pd.cut(
        impact["NewFinalScore"],
        bins=[float("-inf"), 60, 75, float("inf")],
        labels=["IGNORE", "WATCH", "BUY"],
        right=False,
    ).astype(str)
    impact["OldRank"] = impact.groupby("Date")["OldFinalScore"].rank(
        method="min", ascending=False
    )
    impact["NewRank"] = impact.groupby("Date")["NewFinalScore"].rank(
        method="min", ascending=False
    )
    return impact


def run_score_model_impact_analysis(output_path=IMPACT_OUTPUT_PATH):
    scores = build_historical_score_table()
    impact = build_score_model_impact(scores)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    impact.to_csv(path, index=False)
    return impact


if __name__ == "__main__":
    result = run_threshold_analysis()
    impact_result = run_score_model_impact_analysis()
    print(result.to_string(index=False))
    print(f"Output: {OUTPUT_PATH}")
    print(f"Impact output: {IMPACT_OUTPUT_PATH}")
