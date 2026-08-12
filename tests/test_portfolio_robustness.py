import unittest

import numpy as np
import pandas as pd

from portfolio_backtest import simulate_portfolio
from portfolio_robustness import (
    build_benchmark_comparison,
    build_next_open_events,
    calculate_ticker_contribution,
)


class PortfolioRobustnessTests(unittest.TestCase):
    def test_benchmark_alignment_uses_exact_portfolio_dates(self):
        dates = pd.bdate_range("2026-01-01", periods=3)
        equity = pd.DataFrame(
            {"Date": dates, "PortfolioValue": [100000, 101000, 102000]}
        )
        benchmarks = {
            "SPY": self._price_frame(dates, [100, 101, 103]),
            "QQQ": self._price_frame(dates, [200, 198, 204]),
        }

        result = build_benchmark_comparison(equity, benchmark_data=benchmarks)

        self.assertEqual(result["Date"].tolist(), list(dates))
        self.assertAlmostEqual(result.iloc[-1]["SPY_Value"], 103000)
        self.assertAlmostEqual(result.iloc[-1]["QQQ_Cumulative_Return"], 0.02)

    def test_transaction_cost_is_applied_to_entry_and_exit(self):
        dates = pd.bdate_range("2026-01-01", periods=22)
        close = [100] * 20 + [110, 110]
        market = {"AAA": self._price_frame(dates, close)}
        events = self._events(dates)

        trades, equity = simulate_portfolio(
            events,
            market_data=market,
            starting_capital=1000,
            max_positions=1,
            transaction_cost_bps=10,
        )

        self.assertEqual(trades.iloc[0]["Shares"], 9)
        self.assertAlmostEqual(trades.iloc[0]["ProfitLoss"], 88.11, places=6)
        self.assertAlmostEqual(equity.iloc[-1]["PortfolioValue"], 1088.11, places=6)

    def test_next_open_execution_moves_entry_and_exit_dates(self):
        dates = pd.bdate_range("2026-01-01", periods=25)
        frame = self._price_frame(dates, np.linspace(100, 124, len(dates)))
        frame["Open"] = frame["Close"] + 2

        adjusted = build_next_open_events(
            self._events(dates), market_data={"AAA": frame}
        )

        self.assertEqual(pd.Timestamp(adjusted.iloc[0]["EntryDate"]), dates[1])
        self.assertEqual(adjusted.iloc[0]["EntryPrice"], frame.iloc[1]["Open"])
        self.assertEqual(pd.Timestamp(adjusted.iloc[0]["ExitDate_20D"]), dates[21])

    def test_contribution_calculation_reconciles_total_profit(self):
        trades = pd.DataFrame(
            {
                "Ticker": ["AAA", "AAA", "BBB"],
                "ProfitLoss": [100.0, -20.0, 20.0],
                "Return": [0.10, -0.02, 0.02],
            }
        )

        result = calculate_ticker_contribution(trades)

        self.assertAlmostEqual(result["TotalProfitLoss"].sum(), 100.0)
        self.assertAlmostEqual(result["ContributionPercent"].sum(), 1.0)
        aaa = result.loc[result["Ticker"] == "AAA"].iloc[0]
        self.assertEqual(aaa["TradeCount"], 2)
        self.assertAlmostEqual(aaa["WinRate"], 0.5)

    @staticmethod
    def _price_frame(dates, close):
        close = np.asarray(close, dtype=float)
        return pd.DataFrame(
            {
                "Date": pd.DatetimeIndex(dates).strftime("%Y-%m-%d"),
                "Open": close,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": np.full(len(close), 1_000_000),
            }
        )

    @staticmethod
    def _events(dates):
        return pd.DataFrame(
            [
                {
                    "Ticker": "AAA",
                    "EntryDate": dates[0].strftime("%Y-%m-%d"),
                    "EntryPrice": 100.0,
                    "EntryFinalScore": 80.0,
                    "ExitDate_20D": dates[20].strftime("%Y-%m-%d"),
                    "ExitDate_60D": None,
                }
            ]
        )


if __name__ == "__main__":
    unittest.main()
