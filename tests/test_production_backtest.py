import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

import production_backtest
from production_backtest import (
    SIGNAL_COLUMNS,
    build_production_signal_history,
    summarize_production_backtest,
)
from score_threshold_analysis import build_historical_score_table
from trade_signal import generate_signals


class ProductionBacktestTests(unittest.TestCase):
    def test_historical_date_isolation(self):
        original = self._market_data()
        changed = {ticker: frame.copy(deep=True) for ticker, frame in original.items()}
        cutoff = pd.Timestamp("2025-12-01")
        for frame in changed.values():
            future = pd.to_datetime(frame["Date"]) > cutoff
            frame.loc[future, ["Open", "High", "Low", "Close"]] *= 3
            frame.loc[future, "Volume"] *= 2

        before = build_historical_score_table(
            tickers=original, market_data=original
        )
        after = build_historical_score_table(
            tickers=changed, market_data=changed
        )
        columns = [
            "Ticker", "Date", "Score", "RS_Score", "NearHighScore", "FinalScore"
        ]
        assert_frame_equal(
            before.loc[before["Date"] <= cutoff, columns].reset_index(drop=True),
            after.loc[after["Date"] <= cutoff, columns].reset_index(drop=True),
        )

    def test_future_returns_do_not_feed_signal_or_score(self):
        original = self._market_data()
        changed = {ticker: frame.copy(deep=True) for ticker, frame in original.items()}
        cutoff = pd.Timestamp("2025-12-01")
        for frame in changed.values():
            future = pd.to_datetime(frame["Date"]) > cutoff
            frame.loc[future, ["Open", "High", "Low", "Close"]] *= 0.5

        before = build_production_signal_history(
            tickers=original, market_data=original
        )
        after = build_production_signal_history(
            tickers=changed, market_data=changed
        )
        score_columns = [
            column for column in SIGNAL_COLUMNS if not column.startswith("Forward")
        ]
        assert_frame_equal(
            before.loc[pd.to_datetime(before.SignalDate) <= cutoff, score_columns]
            .reset_index(drop=True),
            after.loc[pd.to_datetime(after.SignalDate) <= cutoff, score_columns]
            .reset_index(drop=True),
        )

    @patch("production_backtest.build_historical_score_table")
    def test_signal_generation_matches_production_policy(self, build_scores):
        scores = self._fixed_scores()
        build_scores.return_value = scores
        expected = generate_signals(scores.copy())

        actual = build_production_signal_history()

        expected = expected.loc[expected.TradeSignal.isin(("BUY", "WATCH"))]
        self.assertEqual(
            dict(zip(actual.Ticker, actual.TradeSignal)),
            dict(zip(expected.Ticker, expected.TradeSignal)),
        )
        self.assertEqual(dict(zip(actual.Ticker, actual.TradeSignal))["AAA"], "BUY")
        self.assertEqual(dict(zip(actual.Ticker, actual.TradeSignal))["BBB"], "WATCH")

    @patch("production_backtest.build_historical_score_table")
    def test_output_schema_and_summary(self, build_scores):
        build_scores.return_value = self._fixed_scores()
        signals = build_production_signal_history()
        summary = summarize_production_backtest(signals)

        self.assertEqual(tuple(signals.columns), SIGNAL_COLUMNS)
        self.assertEqual(tuple(summary.columns), production_backtest.SUMMARY_COLUMNS)
        self.assertEqual(summary.iloc[0]["TotalBuySignals"], 1)
        self.assertEqual(summary.iloc[0]["TotalWatchSignals"], 1)

    @staticmethod
    def _market_data():
        dates = pd.bdate_range("2024-08-01", periods=360)
        market = {}
        for ticker, multiplier in (("AAA", 1.0), ("BBB", 1.2)):
            close = np.linspace(100, 200, len(dates)) * multiplier
            market[ticker] = pd.DataFrame(
                {
                    "Date": dates.strftime("%Y-%m-%d"),
                    "Open": close * 0.995,
                    "High": close * 1.01,
                    "Low": close * 0.99,
                    "Close": close,
                    "Volume": np.full(len(dates), 1_000_000),
                }
            )
        return market

    @staticmethod
    def _fixed_scores():
        return pd.DataFrame(
            {
                "Ticker": ["AAA", "BBB", "CCC"],
                "Date": pd.to_datetime(["2026-01-02"] * 3),
                "FinalScore": [80.0, 70.0, 50.0],
                "TrendScore": [90, 70, 20],
                "MomentumScore": [50, 30, 0],
                "RS_Score": [100, 60, 20],
                "NearHighScore": [40, 20, 0],
                "VolumeScore": [10, 0, 0],
                "RiskScore": [50, 50, 50],
                "Volume_Ratio": [1.1, 1.0, 1.0],
                "DistanceToHigh": [0.98, 0.96, 0.80],
                "Close": [110, 105, 90],
                "MA20": [105, 100, 95],
                "MA60": [100, 95, 100],
                "Forward5DReturn": [0.02, 0.01, -0.01],
                "Forward20DReturn": [0.10, 0.05, -0.05],
                "Forward60DReturn": [0.20, 0.10, -0.10],
            }
        )


if __name__ == "__main__":
    unittest.main()
