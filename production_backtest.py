"""Historically reproduce the current production technical signal policy."""

from pathlib import Path

import pandas as pd

from score_threshold_analysis import build_historical_score_table
from trade_signal import generate_signals


PROJECT_ROOT = Path(__file__).resolve().parent
SIGNALS_OUTPUT_PATH = PROJECT_ROOT / "results" / "production_backtest_signals.csv"
SUMMARY_OUTPUT_PATH = PROJECT_ROOT / "results" / "production_backtest_summary.csv"
SIGNAL_COLUMNS = (
    "Ticker",
    "SignalDate",
    "FinalScore",
    "TrendScore",
    "MomentumScore",
    "RSScore",
    "NearHighScore",
    "VolumeScore",
    "RiskScore",
    "TradeSignal",
    "Forward5DReturn",
    "Forward20DReturn",
    "Forward60DReturn",
)
SUMMARY_COLUMNS = (
    "TotalBuySignals",
    "TotalWatchSignals",
    "Average5DForwardReturn",
    "Average20DForwardReturn",
    "Average60DForwardReturn",
    "WinRate20D",
    "MaximumDrawdown20D",
    "Volatility20D",
    "SharpeEstimate20D",
)


def build_production_signal_history(tickers=None, market_data=None):
    """Score each date cross-section and apply the unchanged production policy."""
    scores = build_historical_score_table(tickers=tickers, market_data=market_data)
    if scores.empty:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)
    signaled = []
    for _, date_scores in scores.groupby("Date", sort=True):
        signaled.append(generate_signals(date_scores.copy()))
    history = pd.concat(signaled, ignore_index=True)
    history = history.loc[history["TradeSignal"].isin(("BUY", "WATCH"))].copy()
    output = pd.DataFrame(
        {
            "Ticker": history["Ticker"],
            "SignalDate": history["Date"].dt.strftime("%Y-%m-%d"),
            "FinalScore": history["FinalScore"],
            "TrendScore": history["TrendScore"],
            "MomentumScore": history["MomentumScore"],
            "RSScore": history["RS_Score"],
            "NearHighScore": history["NearHighScore"],
            "VolumeScore": history["VolumeScore"],
            "RiskScore": history["RiskScore"],
            "TradeSignal": history["TradeSignal"],
            "Forward5DReturn": history["Forward5DReturn"],
            "Forward20DReturn": history["Forward20DReturn"],
            "Forward60DReturn": history["Forward60DReturn"],
        }
    )
    return output.loc[:, SIGNAL_COLUMNS].sort_values(
        ["SignalDate", "Ticker"], kind="mergesort"
    ).reset_index(drop=True)


def _maximum_drawdown(signals):
    valid = signals.dropna(subset=["Forward20DReturn"])
    if valid.empty:
        return float("nan")
    cohort_returns = valid.groupby("SignalDate")["Forward20DReturn"].mean()
    daily_equivalent = (1 + cohort_returns.sort_index()).pow(1 / 20) - 1
    equity = (1 + daily_equivalent).cumprod()
    return float((equity / equity.cummax() - 1).min())


def summarize_production_backtest(signals):
    """Summarize BUY observations; WATCH count is retained for policy audit."""
    buys = signals.loc[signals["TradeSignal"] == "BUY"]
    watches = signals.loc[signals["TradeSignal"] == "WATCH"]
    returns20 = buys["Forward20DReturn"].dropna()
    volatility = returns20.std(ddof=1)
    sharpe = (
        returns20.mean() / volatility * ((252 / 20) ** 0.5)
        if pd.notna(volatility) and volatility != 0
        else float("nan")
    )
    return pd.DataFrame(
        [
            {
                "TotalBuySignals": len(buys),
                "TotalWatchSignals": len(watches),
                "Average5DForwardReturn": buys["Forward5DReturn"].mean(),
                "Average20DForwardReturn": returns20.mean(),
                "Average60DForwardReturn": buys["Forward60DReturn"].mean(),
                "WinRate20D": (returns20 > 0).mean(),
                "MaximumDrawdown20D": _maximum_drawdown(buys),
                "Volatility20D": volatility,
                "SharpeEstimate20D": sharpe,
            }
        ],
        columns=SUMMARY_COLUMNS,
    )


def run_production_backtest(
    signals_output_path=SIGNALS_OUTPUT_PATH,
    summary_output_path=SUMMARY_OUTPUT_PATH,
):
    signals = build_production_signal_history()
    summary = summarize_production_backtest(signals)
    signals_path = Path(signals_output_path)
    summary_path = Path(summary_output_path)
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(signals_path, index=False)
    summary.to_csv(summary_path, index=False)
    return signals, summary


if __name__ == "__main__":
    signal_table, summary_table = run_production_backtest()
    print(summary_table.to_string(index=False))
    print(f"Signals: {SIGNALS_OUTPUT_PATH} ({len(signal_table)} rows)")
    print(f"Summary: {SUMMARY_OUTPUT_PATH}")
