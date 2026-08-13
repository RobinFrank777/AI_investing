import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from market_session import completed_daily_bars, latest_completed_session_date


ET = ZoneInfo("America/New_York")


def daily_frame():
    return pd.DataFrame(
        {
            "Open": [100.0, 102.0],
            "High": [103.0, 101.0],
            "Low": [99.0, 100.0],
            "Close": [102.0, 100.5],
            "Volume": [1000, 500],
        },
        index=pd.DatetimeIndex(["2026-08-12", "2026-08-13"]),
    )


class CompletedDailyBarContractTests(unittest.TestCase):
    def test_partial_current_session_is_excluded(self):
        result = completed_daily_bars(
            daily_frame(), datetime(2026, 8, 13, 11, 45, tzinfo=ET)
        )
        self.assertEqual(result.index.strftime("%Y-%m-%d").tolist(), ["2026-08-12"])

    def test_current_session_becomes_eligible_after_completion_buffer(self):
        result = completed_daily_bars(
            daily_frame(), datetime(2026, 8, 13, 16, 15, tzinfo=ET)
        )
        self.assertEqual(len(result), 2)

    def test_historical_completed_rows_are_unchanged(self):
        frame = daily_frame().iloc[:1]
        result = completed_daily_bars(
            frame, datetime(2026, 8, 13, 11, 45, tzinfo=ET)
        )
        pd.testing.assert_frame_equal(result, frame)

    def test_filter_does_not_weaken_completed_ohlc_validation(self):
        frame = daily_frame()
        result = completed_daily_bars(
            frame, datetime(2026, 8, 13, 16, 15, tzinfo=ET)
        )
        self.assertLess(result.loc[pd.Timestamp("2026-08-13"), "High"], 102.0)

    def test_no_ticker_specific_contract(self):
        import inspect
        import market_session

        source = inspect.getsource(market_session)
        for ticker in ("KR", "DKS", "ETN", "LMT", "SPIR"):
            self.assertNotIn(f'"{ticker}"', source)

    def test_intended_as_of_is_latest_completed_new_york_session(self):
        self.assertEqual(
            latest_completed_session_date(
                datetime(2026, 8, 13, 11, 45, tzinfo=ET)
            ).isoformat(),
            "2026-08-12",
        )


if __name__ == "__main__":
    unittest.main()
