import unittest

import numpy as np
import pandas as pd

from portfolio_backtest import EQUITY_COLUMNS, simulate_portfolio


class PortfolioBacktestTests(unittest.TestCase):
    def test_position_accounting_reconciles_every_day(self):
        trades, equity = simulate_portfolio(
            self._events(("AAA",)), market_data=self._market(("AAA",))
        )

        difference = equity["Cash"] + equity["PositionsValue"] - equity["PortfolioValue"]
        self.assertTrue(np.allclose(difference, 0))
        self.assertTrue((equity["Cash"] >= 0).all())
        self.assertEqual(len(trades), 1)

    def test_multiple_simultaneous_entries_are_opened(self):
        tickers = ("AAA", "BBB", "CCC")
        _, equity = simulate_portfolio(
            self._events(tickers), market_data=self._market(tickers)
        )

        self.assertEqual(equity.iloc[0]["Positions"], 3)
        self.assertLessEqual(equity["Positions"].max(), 10)

    def test_exit_date_is_exactly_twenty_trading_rows_later(self):
        dates = pd.bdate_range("2026-01-01", periods=40)
        trades, _ = simulate_portfolio(
            self._events(("AAA",), dates=dates),
            market_data=self._market(("AAA",), dates=dates),
        )

        self.assertEqual(trades.iloc[0]["ExitDate"], dates[20].strftime("%Y-%m-%d"))
        self.assertEqual(trades.iloc[0]["HoldingDays"], 20)
        self.assertEqual(trades.iloc[0]["ExitReason"], "TIME_EXIT_20D")

    def test_equity_curve_schema_and_returns(self):
        _, equity = simulate_portfolio(
            self._events(("AAA",)), market_data=self._market(("AAA",))
        )

        self.assertEqual(tuple(equity.columns), EQUITY_COLUMNS)
        self.assertEqual(equity.iloc[0]["DailyReturn"], 0)
        expected = equity["PortfolioValue"].pct_change().fillna(0)
        self.assertTrue(np.allclose(equity["DailyReturn"], expected))
        self.assertTrue((equity["Drawdown"] <= 0).all())

    @staticmethod
    def _market(tickers, dates=None):
        dates = pd.bdate_range("2026-01-01", periods=40) if dates is None else dates
        result = {}
        for index, ticker in enumerate(tickers):
            close = np.linspace(100 + index * 10, 130 + index * 10, len(dates))
            result[ticker] = pd.DataFrame(
                {
                    "Date": dates.strftime("%Y-%m-%d"),
                    "Open": close,
                    "High": close + 1,
                    "Low": close - 1,
                    "Close": close,
                    "Volume": np.full(len(dates), 1_000_000),
                }
            )
        return result

    @staticmethod
    def _events(tickers, dates=None):
        dates = pd.bdate_range("2026-01-01", periods=40) if dates is None else dates
        rows = []
        for index, ticker in enumerate(tickers):
            rows.append(
                {
                    "Ticker": ticker,
                    "EntryDate": dates[0].strftime("%Y-%m-%d"),
                    "EntryPrice": 100 + index * 10,
                    "EntryFinalScore": 80 - index,
                    "ExitDate_20D": dates[20].strftime("%Y-%m-%d"),
                    "ExitDate_60D": None,
                }
            )
        return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
