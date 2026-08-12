import unittest

import pandas as pd

from score import SCORE_MODEL_VERSION
from score_threshold_analysis import analyze_thresholds, build_score_model_impact


class ScoreThresholdAnalysisTests(unittest.TestCase):
    def test_threshold_counts_and_forward_metrics(self):
        scores = pd.DataFrame(
            {
                "Ticker": ["AAA", "BBB", "AAA", "BBB"],
                "Date": pd.to_datetime(
                    ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"]
                ),
                "FinalScore": [80.0, 70.0, 60.0, 40.0],
                "Forward5DReturn": [0.01, -0.02, 0.03, 0.04],
                "Forward20DReturn": [0.10, -0.05, 0.20, 0.01],
                "Forward60DReturn": [0.30, -0.10, 0.40, 0.02],
            }
        )

        result = analyze_thresholds(scores, thresholds=(60, 75))

        sixty = result.iloc[0]
        self.assertEqual(sixty["SignalCount"], 3)
        self.assertEqual(sixty["EligibleObservationCount"], 4)
        self.assertAlmostEqual(sixty["UniversePercentage"], 0.75)
        self.assertAlmostEqual(sixty["Average20DForwardReturn"], 0.25 / 3)
        self.assertAlmostEqual(sixty["WinRate20D"], 2 / 3)
        seventy_five = result.iloc[1]
        self.assertEqual(seventy_five["SignalCount"], 1)
        self.assertAlmostEqual(seventy_five["Average5DForwardReturn"], 0.01)

    def test_missing_forward_returns_are_not_filled(self):
        scores = pd.DataFrame(
            {
                "Ticker": ["AAA", "BBB"],
                "Date": pd.to_datetime(["2026-01-01", "2026-01-01"]),
                "FinalScore": [80.0, 80.0],
                "Forward5DReturn": [0.01, None],
                "Forward20DReturn": [0.10, None],
                "Forward60DReturn": [None, None],
            }
        )

        result = analyze_thresholds(scores, thresholds=(75,)).iloc[0]

        self.assertEqual(result["SignalCount"], 2)
        self.assertAlmostEqual(result["Average5DForwardReturn"], 0.01)
        self.assertAlmostEqual(result["Average20DForwardReturn"], 0.10)
        self.assertTrue(pd.isna(result["Average60DForwardReturn"]))

    def test_score_model_impact_is_constant_and_preserves_rank(self):
        scores = pd.DataFrame(
            {
                "Ticker": ["AAA", "BBB", "AAA", "BBB"],
                "Date": pd.to_datetime(
                    ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"]
                ),
                "ScoreModelVersion": [SCORE_MODEL_VERSION] * 4,
                "FinalScore": [75.0, 60.0, 59.0, 40.0],
            }
        )

        impact = build_score_model_impact(scores)

        self.assertEqual(impact["FinalScoreShift"].tolist(), [-5.25] * 4)
        self.assertEqual(impact["NewThresholdBand"].tolist(), ["BUY", "WATCH", "IGNORE", "IGNORE"])
        self.assertTrue((impact["OldRank"] == impact["NewRank"]).all())


if __name__ == "__main__":
    unittest.main()
