import unittest

import numpy as np
import pandas as pd

from trade_event_backtest import EVENT_COLUMNS, build_trade_events


class TradeEventBacktestTests(unittest.TestCase):
    def test_consecutive_buy_signals_create_one_entry(self):
        signals = self._signals(["BUY", "BUY", "BUY"])

        events = build_trade_events(signals, market_data=self._market())

        self.assertEqual(len(events), 1)
        self.assertEqual(events.iloc[0]["EntryDate"], "2026-01-01")

    def test_watch_to_buy_creates_entry(self):
        signals = self._signals(["WATCH", "BUY"])

        events = build_trade_events(signals, market_data=self._market())

        self.assertEqual(len(events), 1)
        self.assertEqual(events.iloc[0]["EntryDate"], "2026-01-02")

    def test_ignore_gap_to_buy_creates_entry(self):
        signals = self._signals(["BUY", "BUY", "BUY"], positions=(0, 1, 3))

        events = build_trade_events(signals, market_data=self._market())

        self.assertEqual(len(events), 2)
        self.assertEqual(events["EntryDate"].tolist(), ["2026-01-01", "2026-01-06"])

    def test_output_schema_and_missing_future_horizons(self):
        signals = self._signals(["BUY"])

        events = build_trade_events(signals, market_data=self._market(rows=10))

        self.assertEqual(tuple(events.columns), EVENT_COLUMNS)
        self.assertFalse(pd.isna(events.iloc[0]["ExitDate_5D"]))
        self.assertTrue(pd.isna(events.iloc[0]["ExitDate_20D"]))
        self.assertTrue(pd.isna(events.iloc[0]["Return_60D"]))
        self.assertTrue(pd.isna(events.iloc[0]["MaximumFavorableExcursion"]))

    @staticmethod
    def _market(rows=80):
        dates = pd.bdate_range("2026-01-01", periods=rows)
        close = np.linspace(100, 180, rows)
        return {
            "AAA": pd.DataFrame(
                {
                    "Date": dates.strftime("%Y-%m-%d"),
                    "Open": close,
                    "High": close + 1,
                    "Low": close - 1,
                    "Close": close,
                    "Volume": np.full(rows, 1_000_000),
                }
            )
        }

    @staticmethod
    def _signals(states, positions=None):
        dates = pd.bdate_range("2026-01-01", periods=10)
        if positions is None:
            positions = tuple(range(len(states)))
        rows = []
        for state, position in zip(states, positions):
            rows.append(
                {
                    "Ticker": "AAA",
                    "SignalDate": dates[position],
                    "FinalScore": 80 if state == "BUY" else 65,
                    "TrendScore": 90,
                    "MomentumScore": 40,
                    "RSScore": 90,
                    "NearHighScore": 30,
                    "VolumeScore": 10,
                    "RiskScore": 50,
                    "TradeSignal": state,
                }
            )
        return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
