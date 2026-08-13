import unittest
from unittest.mock import patch

import pandas as pd

import config
import combined_scoring
import rank_stocks_v2
import universe_metadata as subject


class UniverseMetadataTests(unittest.TestCase):
    def test_authoritative_value_comes_from_config(self):
        tagged = subject.tag_current_universe(pd.DataFrame({"Ticker": ["A"]}))
        self.assertEqual(tagged.at[0, "UniverseVersion"], config.PRIMARY_UNIVERSE_VERSION)

    def test_match_mismatch_and_missing(self):
        self.assertEqual(subject.universe_compatibility(config.PRIMARY_UNIVERSE_VERSION), subject.MATCH)
        self.assertEqual(subject.universe_compatibility("legacy-19"), subject.MISMATCH)
        self.assertEqual(subject.universe_compatibility(None), subject.MISSING)
        self.assertEqual(subject.dataframe_universe_compatibility(pd.DataFrame({"Ticker": ["A"]})), subject.MISSING)

    def test_missing_is_not_current_and_is_not_rewritten(self):
        legacy = pd.DataFrame({"Ticker": ["A"], "FinalScore": [42.0]})
        before = legacy.copy(deep=True)
        self.assertEqual(subject.dataframe_universe_compatibility(legacy), subject.MISSING)
        pd.testing.assert_frame_equal(legacy, before)

    def test_tagging_changes_neither_membership_nor_values(self):
        original = pd.DataFrame({"Ticker": ["B", "A"], "FinalScore": [75.0, 50.0], "TradeSignal": ["BUY", "WATCH"]})
        tagged = subject.tag_current_universe(original)
        pd.testing.assert_frame_equal(tagged.drop(columns=["UniverseVersion"]), original)
        self.assertEqual(tagged["Ticker"].tolist(), original["Ticker"].tolist())

    def test_combined_score_producer_tags_without_changing_score(self):
        model = pd.DataFrame({"Ticker": ["A"], "BacktestScore": [80.0]})
        fundamental = pd.DataFrame({"Ticker": ["A"], "FundamentalScore": [60.0], "FundamentalRating": ["GOOD"]})
        result = combined_scoring.calculate_combined_score(model, fundamental)
        expected = round(
            80.0 * config.BACKTEST_SCORE_WEIGHT
            + 60.0 * config.FUNDAMENTAL_SCORE_WEIGHT,
            2,
        )
        self.assertEqual(result.at[0, "CombinedScore"], expected)
        self.assertEqual(result.at[0, "UniverseVersion"], config.PRIMARY_UNIVERSE_VERSION)

    def test_ranking_producer_tags_without_changing_score_or_signal(self):
        scored = pd.DataFrame({"Ticker": ["A"], "FinalScore": [71.5]})
        signaled = scored.assign(TradeSignal="BUY")
        with patch.object(rank_stocks_v2, "process_single_stock", return_value={"Ticker": "A"}), patch.object(
            rank_stocks_v2, "calculate_final_score", return_value=scored
        ), patch.object(
            rank_stocks_v2, "generate_signals", return_value=signaled
        ), patch.object(rank_stocks_v2, "generate_reason", new=lambda row: "unchanged"):
            result = rank_stocks_v2.rank_stocks(["A"])
        self.assertEqual(result.at[0, "FinalScore"], 71.5)
        self.assertEqual(result.at[0, "TradeSignal"], "BUY")
        self.assertEqual(result.at[0, "UniverseVersion"], config.PRIMARY_UNIVERSE_VERSION)


if __name__ == "__main__":
    unittest.main()
