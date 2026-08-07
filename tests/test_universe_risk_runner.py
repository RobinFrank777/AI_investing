import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import universe_risk_runner as subject


def risk_row(ticker, volatility=0.2, drawdown=-0.1, sharpe=1.5, status="PASS"):
    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "AnnualizedVolatility": volatility,
                "MaxDrawdown": drawdown,
                "SharpeRatio": sharpe,
                "RiskStatus": status,
                "RiskError": "",
            }
        ]
    )


class UniverseRiskRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()
        self.output = self.root / "results" / "universe150_risk_raw.csv"
        self.universe = pd.DataFrame({"ticker": ["A", "B", "WATCH"]})

    def loader_patches(self, active=None):
        symbols = ["A", "B"] if active is None else active
        return (
            patch.object(subject.universe_loader, "load_universe", return_value=self.universe),
            patch.object(subject.universe_loader, "get_active_symbols", return_value=symbols),
        )

    def test_processes_active_symbols_only_and_calls_risk_engine(self):
        load_patch, active_patch = self.loader_patches()
        with load_patch as load, active_patch as active, patch.object(
            subject, "_observation_count", side_effect=[300, 280]
        ), patch.object(
            subject.risk_engine,
            "calculate_risk",
            side_effect=[risk_row("A"), risk_row("B")],
        ) as calculate:
            result = subject.build_universe_risk_table("universe.csv", self.data_dir)
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
        self.assertEqual(result["ObservationCount"].tolist(), [300, 280])

    def test_failed_ticker_is_recorded_and_later_ticker_continues(self):
        load_patch, active_patch = self.loader_patches(active=["A", "B", "C"])
        with load_patch, active_patch, patch.object(
            subject, "_observation_count", return_value=0
        ), patch.object(
            subject.risk_engine,
            "calculate_risk",
            side_effect=[risk_row("A"), RuntimeError("bad file"), risk_row("C")],
        ) as calculate:
            result = subject.build_universe_risk_table(data_dir=self.data_dir)
        self.assertEqual(calculate.call_count, 3)
        self.assertEqual(result["Status"].tolist(), ["PASS", "FAILED", "PASS"])
        self.assertTrue(pd.isna(result.at[1, "SharpeRatio"]))

    def test_engine_failed_status_is_preserved(self):
        load_patch, active_patch = self.loader_patches(active=["A"])
        with load_patch, active_patch, patch.object(
            subject, "_observation_count", return_value=10
        ), patch.object(
            subject.risk_engine,
            "calculate_risk",
            return_value=risk_row("A", None, None, None, "FAILED"),
        ):
            result = subject.build_universe_risk_table(data_dir=self.data_dir)
        self.assertEqual(result.at[0, "Status"], "FAILED")
        self.assertEqual(result.at[0, "ObservationCount"], 10)

    def test_missing_metric_is_partial(self):
        load_patch, active_patch = self.loader_patches(active=["A"])
        with load_patch, active_patch, patch.object(
            subject, "_observation_count", return_value=252
        ), patch.object(
            subject.risk_engine,
            "calculate_risk",
            return_value=risk_row("A", sharpe=None, status="PASS"),
        ):
            result = subject.build_universe_risk_table(data_dir=self.data_dir)
        self.assertEqual(result.at[0, "Status"], "PARTIAL")
        self.assertTrue(pd.isna(result.at[0, "SharpeRatio"]))

    def test_observation_count_reads_csv_rows(self):
        path = self.data_dir / "A.csv"
        pd.DataFrame({"Date": [1, 2, 3], "Close": [10, 11, 12]}).to_csv(path, index=False)
        self.assertEqual(subject._observation_count(path), 3)
        self.assertEqual(subject._observation_count(self.data_dir / "missing.csv"), 0)

    def test_empty_active_universe_returns_fixed_schema(self):
        load_patch, active_patch = self.loader_patches(active=[])
        with load_patch, active_patch, patch.object(
            subject.risk_engine, "calculate_risk"
        ) as calculate:
            result = subject.build_universe_risk_table(data_dir=self.data_dir)
        calculate.assert_not_called()
        self.assertTrue(result.empty)
        self.assertEqual(result.columns.tolist(), list(subject.OUTPUT_COLUMNS))

    def test_run_saves_fixed_output_columns(self):
        table = pd.DataFrame(
            [["A", 0.2, -0.1, 1.5, 300, "PASS"]],
            columns=subject.OUTPUT_COLUMNS,
        )
        with patch.object(subject, "build_universe_risk_table", return_value=table):
            result = subject.run_universe_risk(output_path=self.output)
        self.assertEqual(result["output_path"], str(self.output))
        self.assertEqual(result["summary"], {"total": 1, "pass": 1, "partial": 0, "failed": 0})
        saved = pd.read_csv(self.output)
        self.assertEqual(saved.columns.tolist(), list(subject.OUTPUT_COLUMNS))

    def test_no_ranking_normalization_scoring_or_execution_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "factor_ranking",
            "factor_normalization",
            "CompositeScore",
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
