import unittest

import pandas as pd
from pandas.testing import assert_series_equal

from score import (
    SCORE_DIAGNOSTIC_COLUMNS,
    build_score_diagnostic_table,
    calculate_final_score,
    calculate_rank_score,
    calculate_rank_score_diagnostics,
)
from trade_signal import generate_signals


class ScoreDiagnosticsTests(unittest.TestCase):
    def test_score_decomposition_preserves_raw_score_formula(self):
        inputs = (110, 100, 90, 0.10, 0.20, 1.6, 105, 0.97, 2, 1, 0.5)

        score, confidence = calculate_rank_score(*inputs)
        diagnostics = calculate_rank_score_diagnostics(*inputs)

        expected_return = 0.10 * 70 + 0.20 * 30
        expected_momentum = expected_return + 40
        expected_score = 110 * 0.40 + expected_momentum * 0.25 + 20 * 0.20 + 50 * 0.15
        self.assertEqual(diagnostics["TrendScore"], 110)
        self.assertEqual(diagnostics["MACDContribution"], 40)
        self.assertAlmostEqual(
            diagnostics["ReturnMomentumContribution"], expected_return
        )
        self.assertAlmostEqual(diagnostics["MomentumScore"], expected_momentum)
        self.assertEqual(diagnostics["VolumeScore"], 20)
        self.assertEqual(diagnostics["RiskScore"], 50)
        self.assertAlmostEqual(diagnostics["RawScore"], expected_score)
        self.assertAlmostEqual(score, expected_score)
        self.assertEqual(confidence, diagnostics["Confidence"])

    def test_diagnostic_table_generates_all_fields_and_preserves_missing_values(self):
        frame = self._fixed_rank_fixture()
        scored = calculate_final_score(frame)
        diagnostics = build_score_diagnostic_table(scored)

        self.assertEqual(tuple(diagnostics.columns), SCORE_DIAGNOSTIC_COLUMNS)
        self.assertTrue(pd.isna(diagnostics.loc[1, "MACDContribution"]))
        assert_series_equal(
            diagnostics["FinalScore"],
            scored["FinalScore"],
            check_names=False,
        )

    def test_missing_component_is_reported_explicitly(self):
        frame = self._fixed_rank_fixture().drop(columns=["RiskScore"])
        scored = calculate_final_score(frame)

        with self.assertRaisesRegex(
            ValueError, "score diagnostics missing required components: RiskScore"
        ):
            build_score_diagnostic_table(scored)

    def test_diagnostics_do_not_change_final_score_rank_or_signal(self):
        frame = self._fixed_rank_fixture()
        scored = generate_signals(calculate_final_score(frame.copy()))
        ranked = scored.sort_values("FinalScore", ascending=False).reset_index(drop=True)
        before_final = ranked["FinalScore"].copy()
        before_order = ranked["Ticker"].tolist()
        before_signal = ranked["TradeSignal"].copy()

        diagnostics = build_score_diagnostic_table(ranked)

        self.assertEqual(before_order, ["AAA", "BBB", "CCC"])
        self.assertEqual(
            before_final.round(6).tolist(), [80.0, 60.133333, 20.666667]
        )
        self.assertEqual(before_signal.tolist(), ["BUY", "WATCH", "IGNORE"])
        assert_series_equal(
            diagnostics["FinalScore"], before_final, check_names=False
        )
        self.assertEqual(ranked["Ticker"].tolist(), before_order)
        assert_series_equal(ranked["TradeSignal"], before_signal)

    @staticmethod
    def _fixed_rank_fixture():
        return pd.DataFrame(
            {
                "Ticker": ["AAA", "BBB", "CCC"],
                "MarketDataDate": ["2026-08-11"] * 3,
                "TrendScore": [90, 60, 20],
                "MomentumScore": [40, 20, -10],
                "MACDContribution": [40, None, 0],
                "ReturnMomentumContribution": [0, 20, -10],
                "VolumeScore": [20, 10, 0],
                "RiskScore": [50, 50, 50],
                "RawScore": [80, 64, 20],
                "Score": [80, 64, 20],
                "60Day_Return": [0.30, 0.20, 0.10],
                "DistanceToHigh": [1.00, 0.95, 0.80],
                "Volume_Ratio": [1.1, 0.9, 0.5],
                "Close": [110, 100, 80],
                "MA20": [100, 95, 90],
                "MA60": [90, 90, 100],
            }
        )


if __name__ == "__main__":
    unittest.main()
