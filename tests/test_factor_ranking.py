import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import factor_ranking


def raw_factors():
    return pd.DataFrame(
        {
            "Ticker": ["A", "B", "C"],
            "TrendValue": [0.10, 0.20, 0.30],
            "MomentumValue": [0.30, 0.20, 0.10],
            "Volatility20D": [0.30, 0.20, 0.10],
        }
    )


class FactorRankingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_raw(self, frame=None):
        path = self.root / "universe150_factor_raw.csv"
        (raw_factors() if frame is None else frame).to_csv(path, index=False)
        return path

    def test_loads_raw_factor_csv(self):
        loaded = factor_ranking.load_raw_factors(self.write_raw())
        pd.testing.assert_frame_equal(loaded, raw_factors())

    def test_normalization_directions(self):
        result = factor_ranking.build_factor_ranking(raw_factors())
        indexed = result.set_index("Ticker")
        self.assertLess(indexed.at["A", "TrendScore"], indexed.at["C", "TrendScore"])
        self.assertGreater(indexed.at["A", "MomentumScore"], indexed.at["C", "MomentumScore"])
        self.assertLess(indexed.at["A", "LowVolScore"], indexed.at["C", "LowVolScore"])

    def test_lowest_volatility_gets_highest_low_vol_score(self):
        result = factor_ranking.build_factor_ranking(raw_factors()).set_index("Ticker")
        self.assertEqual(result.at["C", "LowVolScore"], 1.0)
        self.assertEqual(result.at["A", "LowVolScore"], 1 / 3)

    def test_composite_uses_fixed_weights(self):
        result = factor_ranking.build_factor_ranking(raw_factors()).set_index("Ticker")
        row = result.loc["C"]
        expected = (
            row["TrendScore"] * 0.35
            + row["MomentumScore"] * 0.35
            + row["LowVolScore"] * 0.30
        )
        self.assertAlmostEqual(row["CompositeScore"], expected)

    def test_rank_is_descending_composite_score(self):
        result = factor_ranking.build_factor_ranking(raw_factors())
        best = result.loc[result["CompositeScore"].idxmax()]
        worst = result.loc[result["CompositeScore"].idxmin()]
        self.assertEqual(best["Rank"], 1.0)
        self.assertGreater(worst["Rank"], best["Rank"])

    def test_missing_factor_remains_unranked(self):
        raw = raw_factors()
        raw.loc[1, "MomentumValue"] = None
        result = factor_ranking.build_factor_ranking(raw)
        self.assertTrue(pd.isna(result.at[1, "MomentumScore"]))
        self.assertTrue(pd.isna(result.at[1, "CompositeScore"]))
        self.assertTrue(pd.isna(result.at[1, "Rank"]))

    def test_existing_normalizer_is_reused_with_correct_directions(self):
        values = [
            pd.Series([0.1, 0.2, 0.3]),
            pd.Series([0.3, 0.2, 0.1]),
            pd.Series([0.3, 0.2, 0.1]),
        ]
        with patch.object(
            factor_ranking, "normalize_factor_series", side_effect=values
        ) as normalize:
            factor_ranking.build_factor_ranking(raw_factors())
        self.assertEqual(
            [item.kwargs["higher_is_better"] for item in normalize.call_args_list],
            [True, True, False],
        )

    def test_missing_required_column_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MomentumValue"):
            factor_ranking.build_factor_ranking(
                raw_factors().drop(columns=["MomentumValue"])
            )

    def test_run_saves_ranking_artifact(self):
        output = self.root / "results" / "universe150_factor_ranking.csv"
        result = factor_ranking.run_factor_ranking(self.write_raw(), output)
        self.assertEqual(result["output_path"], str(output))
        self.assertTrue(output.is_file())
        saved = pd.read_csv(output)
        self.assertEqual(saved.columns.tolist(), list(factor_ranking.RANKING_COLUMNS))
        self.assertEqual(result["summary"], {"total": 3, "ranked": 3, "unranked": 0})

    def test_no_trading_portfolio_or_watchlist_dependency(self):
        source = Path(factor_ranking.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "watchlist.csv",
            "universe_loader",
            "load_active_universe",
            "import portfolio",
            "import order",
            "import broker",
            "import backtest",
        )
        for reference in forbidden_references:
            with self.subTest(reference=reference):
                self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
