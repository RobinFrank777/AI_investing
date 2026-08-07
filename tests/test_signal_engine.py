import tempfile
import unittest
from pathlib import Path

import pandas as pd

import signal_engine
from factor_ranking import RANKING_COLUMNS


def ranking_frame():
    return pd.DataFrame(
        [
            {
                "Ticker": "A",
                "TrendValue": 0.10,
                "MomentumValue": 0.20,
                "Volatility20D": 0.15,
                "TrendScore": 0.80,
                "MomentumScore": 0.60,
                "LowVolScore": 0.90,
                "CompositeScore": 0.86,
                "Rank": 1.0,
            },
            {
                "Ticker": "B",
                "TrendValue": -0.10,
                "MomentumValue": -0.20,
                "Volatility20D": 0.40,
                "TrendScore": 0.40,
                "MomentumScore": 0.30,
                "LowVolScore": 0.20,
                "CompositeScore": 0.50,
                "Rank": 2.0,
            },
        ],
        columns=RANKING_COLUMNS,
    )


class SignalEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_ranking(self, frame=None):
        path = self.root / "universe150_factor_ranking.csv"
        (ranking_frame() if frame is None else frame).to_csv(path, index=False)
        return path

    def test_trend_signal_boundaries(self):
        self.assertEqual(signal_engine.trend_signal(0.75), "STRONG")
        self.assertEqual(signal_engine.trend_signal(0.50), "NORMAL")
        self.assertEqual(signal_engine.trend_signal(0.4999), "WEAK")

    def test_momentum_signal_boundaries(self):
        self.assertEqual(signal_engine.momentum_signal(0.75), "POSITIVE")
        self.assertEqual(signal_engine.momentum_signal(0.50), "NEUTRAL")
        self.assertEqual(signal_engine.momentum_signal(0.4999), "NEGATIVE")

    def test_volatility_signal_direction_and_boundaries(self):
        self.assertEqual(signal_engine.volatility_signal(0.75), "LOW")
        self.assertEqual(signal_engine.volatility_signal(0.50), "NORMAL")
        self.assertEqual(signal_engine.volatility_signal(0.4999), "HIGH")

    def test_composite_signal_boundaries(self):
        cases = (
            (0.85, "A"),
            (0.8499, "B"),
            (0.70, "B"),
            (0.6999, "C"),
            (0.55, "C"),
            (0.5499, "D"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(signal_engine.composite_signal(value), expected)

    def test_normal_input_preserves_original_fields_rank_and_order(self):
        ranking = ranking_frame()
        before = ranking.copy(deep=True)
        result = signal_engine.build_signals(ranking)
        pd.testing.assert_frame_equal(ranking, before)
        pd.testing.assert_frame_equal(result.loc[:, RANKING_COLUMNS], before)
        self.assertEqual(result["Ticker"].tolist(), ["A", "B"])
        self.assertEqual(result["Rank"].tolist(), [1.0, 2.0])
        self.assertEqual(result["TrendSignal"].tolist(), ["STRONG", "WEAK"])
        self.assertEqual(result["CompositeSignal"].tolist(), ["A", "D"])

    def test_missing_scores_map_to_unknown_without_recalculation(self):
        ranking = ranking_frame()
        ranking.loc[0, ["TrendScore", "MomentumScore", "LowVolScore", "CompositeScore"]] = None
        result = signal_engine.build_signals(ranking)
        self.assertEqual(result.loc[0, list(signal_engine.SIGNAL_COLUMNS)].tolist(), ["UNKNOWN"] * 4)
        self.assertTrue(pd.isna(result.at[0, "CompositeScore"]))

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MomentumScore"):
            signal_engine.build_signals(
                ranking_frame().drop(columns=["MomentumScore"])
            )

    def test_empty_data_returns_empty_table_with_signal_columns(self):
        empty = pd.DataFrame(columns=RANKING_COLUMNS)
        result = signal_engine.build_signals(empty)
        self.assertTrue(result.empty)
        self.assertEqual(
            result.columns.tolist(), list(RANKING_COLUMNS) + list(signal_engine.SIGNAL_COLUMNS)
        )

    def test_run_reads_and_saves_signal_artifact(self):
        output = self.root / "results" / "universe150_signal.csv"
        result = signal_engine.run_signal_engine(self.write_ranking(), output)
        self.assertEqual(result["output_path"], str(output))
        self.assertEqual(result["summary"], {"rows": 2})
        saved = pd.read_csv(output)
        self.assertEqual(saved["CompositeSignal"].tolist(), ["A", "D"])

    def test_no_production_or_execution_dependencies(self):
        source = Path(signal_engine.__file__).read_text(encoding="utf-8").lower()
        forbidden_references = (
            "import portfolio",
            "import watchlist",
            "import broker",
            "import order",
            "import run_all",
        )
        for reference in forbidden_references:
            with self.subTest(reference=reference):
                self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
