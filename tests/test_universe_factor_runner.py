import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import universe_factor_runner as subject


def factor_row(ticker, trend=0.1, momentum=0.2, volatility=0.3):
    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "TrendValue": trend,
                "MomentumValue": momentum,
                "Volatility20D": volatility,
            }
        ]
    )


class UniverseFactorRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        self.output = self.root / "results" / "universe150_factor_raw.csv"
        self.universe = pd.DataFrame({"ticker": ["A", "B", "WATCH"]})

    def loader_patches(self, active=None):
        symbols = ["A", "B"] if active is None else active
        load = patch.object(
            subject.universe_loader, "load_universe", return_value=self.universe
        )
        get_active = patch.object(
            subject.universe_loader, "get_active_symbols", return_value=symbols
        )
        return load, get_active

    def test_processes_active_symbols_only_in_order(self):
        load_patch, active_patch = self.loader_patches()
        with load_patch as load, active_patch as active, patch.object(
            subject.factor_engine,
            "calculate_factors",
            side_effect=[factor_row("A"), factor_row("B")],
        ) as calculate:
            result = subject.build_universe_factor_table("universe.csv", self.data_dir)
        load.assert_called_once_with("universe.csv")
        active.assert_called_once_with(self.universe)
        self.assertEqual(
            calculate.call_args_list,
            [
                call(self.data_dir / "A.csv", ticker="A"),
                call(self.data_dir / "B.csv", ticker="B"),
            ],
        )
        self.assertEqual(result["Ticker"].tolist(), ["A", "B"])
        self.assertNotIn("WATCH", result["Ticker"].tolist())

    def test_one_ticker_failure_does_not_stop_execution(self):
        load_patch, active_patch = self.loader_patches(active=["A", "B", "C"])
        with load_patch, active_patch, patch.object(
            subject.factor_engine,
            "calculate_factors",
            side_effect=[factor_row("A"), ValueError("bad data"), factor_row("C")],
        ) as calculate:
            result = subject.build_universe_factor_table(data_dir=self.data_dir)
        self.assertEqual(calculate.call_count, 3)
        self.assertEqual(result["FactorStatus"].tolist(), ["PASS", "FAILED", "PASS"])
        self.assertIn("ValueError: bad data", result.iloc[1]["FactorError"])
        self.assertTrue(pd.isna(result.iloc[1]["TrendValue"]))

    def test_missing_factor_values_are_partial_not_ranked(self):
        load_patch, active_patch = self.loader_patches(active=["A"])
        with load_patch, active_patch, patch.object(
            subject.factor_engine,
            "calculate_factors",
            return_value=factor_row("A", trend=None),
        ):
            result = subject.build_universe_factor_table(data_dir=self.data_dir)
        self.assertEqual(result.at[0, "FactorStatus"], "PARTIAL")
        self.assertIn("TrendValue", result.at[0, "FactorError"])
        self.assertNotIn("Rank", result.columns)
        self.assertNotIn("Percentile", "".join(result.columns))

    def test_empty_active_universe_returns_empty_fixed_schema(self):
        load_patch, active_patch = self.loader_patches(active=[])
        with load_patch, active_patch, patch.object(
            subject.factor_engine, "calculate_factors"
        ) as calculate:
            result = subject.build_universe_factor_table(data_dir=self.data_dir)
        calculate.assert_not_called()
        self.assertTrue(result.empty)
        self.assertEqual(result.columns.tolist(), list(subject.RAW_FACTOR_COLUMNS))

    def test_malformed_factor_result_is_isolated(self):
        load_patch, active_patch = self.loader_patches(active=["A", "B"])
        with load_patch, active_patch, patch.object(
            subject.factor_engine,
            "calculate_factors",
            side_effect=[pd.DataFrame(), factor_row("B")],
        ):
            result = subject.build_universe_factor_table(data_dir=self.data_dir)
        self.assertEqual(result["FactorStatus"].tolist(), ["FAILED", "PASS"])
        self.assertIn("single-row DataFrame", result.at[0, "FactorError"])

    def test_run_saves_expected_output_without_index(self):
        table = pd.DataFrame(
            [
                {
                    "Ticker": "A",
                    "TrendValue": 0.1,
                    "MomentumValue": 0.2,
                    "Volatility20D": 0.3,
                    "FactorStatus": "PASS",
                    "FactorError": "",
                }
            ],
            columns=subject.RAW_FACTOR_COLUMNS,
        )
        with patch.object(
            subject, "build_universe_factor_table", return_value=table
        ):
            result = subject.run_universe_factors(output_path=self.output)
        self.assertEqual(result["output_path"], str(self.output))
        self.assertEqual(result["summary"], {"total": 1, "pass": 1, "partial": 0, "failed": 0})
        saved = pd.read_csv(self.output)
        self.assertEqual(saved.columns.tolist(), list(subject.RAW_FACTOR_COLUMNS))
        self.assertEqual(saved["Ticker"].tolist(), ["A"])

    def test_no_normalization_ranking_or_trading_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "factor_normalization",
            "factor_composite",
            "load_active_universe",
            "watchlist.csv",
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
