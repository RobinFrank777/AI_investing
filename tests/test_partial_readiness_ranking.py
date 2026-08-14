import unittest
from unittest.mock import patch

import pandas as pd

import rank_stocks_v2


class PartialReadinessRankingTests(unittest.TestCase):
    def readiness(self):
        return pd.DataFrame([
            {
                "Ticker": "CURRENT", "Ready": True, "Status": "READY",
                "Reason": "READY", "LatestAcceptedDate": "2026-08-13", "Rows": 300,
            },
            {
                "Ticker": "STALE_HIGH_SCORE", "Ready": False,
                "Status": "PROVIDER_REJECTED", "Reason": "STALE_MARKET_DATA",
                "LatestAcceptedDate": "2026-08-12", "Rows": 300,
            },
        ])

    def test_only_ready_current_subset_reaches_cross_sectional_ranking(self):
        ranked = pd.DataFrame({
            "Ticker": ["CURRENT"], "FinalScore": [80.0], "TradeSignal": ["WATCH"],
        })
        with (
            patch.object(rank_stocks_v2, "build_data_readiness", return_value=self.readiness()),
            patch.object(rank_stocks_v2, "save_data_readiness"),
            patch.object(rank_stocks_v2, "latest_completed_session_date", return_value=pd.Timestamp("2026-08-13").date()),
            patch.object(rank_stocks_v2, "print_validation_summary"),
            patch.object(rank_stocks_v2, "rank_stocks", return_value=ranked) as ranker,
            patch.object(rank_stocks_v2, "print_signal_summary"),
            patch.object(rank_stocks_v2, "build_score_diagnostic_table", return_value=pd.DataFrame()),
            patch.object(rank_stocks_v2, "save_daily_report"),
            patch.object(pd.DataFrame, "to_csv"),
        ):
            result = rank_stocks_v2.run_ranking_pipeline()
        ranker.assert_called_once_with(["CURRENT"])
        self.assertEqual(result["Ticker"].tolist(), ["CURRENT"])

    def test_no_ready_subset_fails_instead_of_reusing_old_scores(self):
        unavailable = self.readiness().assign(Ready=False)
        with (
            patch.object(rank_stocks_v2, "build_data_readiness", return_value=unavailable),
            patch.object(rank_stocks_v2, "save_data_readiness"),
            patch.object(rank_stocks_v2, "latest_completed_session_date", return_value=pd.Timestamp("2026-08-13").date()),
            patch.object(rank_stocks_v2, "print_validation_summary"),
            patch.object(rank_stocks_v2, "rank_stocks") as ranker,
            self.assertRaisesRegex(RuntimeError, "No valid stock data"),
        ):
            rank_stocks_v2.run_ranking_pipeline()
        ranker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
