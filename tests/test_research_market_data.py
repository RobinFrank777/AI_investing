import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import research_market_data as subject


def readiness_rows(specification):
    rows = []
    for ticker, state in specification:
        exists = state != "missing"
        columns = state not in ("missing", "invalid")
        history = state == "ready"
        rows.append(
            {
                "Ticker": ticker,
                "FilePath": f"data/{ticker}.csv",
                "FileExists": exists,
                "RequiredColumnsPresent": columns,
                "MissingColumns": "Volume" if state == "invalid" else "",
                "HistoryRows": 252 if history else 100 if exists else 0,
                "MinimumHistoryRows": 252,
                "HistorySufficient": history,
                "Ready": state == "ready",
                "Error": "" if state == "ready" else state,
            }
        )
    return pd.DataFrame(rows)


class ResearchMarketDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "readiness.csv"
        self.universe = pd.DataFrame({"ticker": ["A", "B", "C", "D"]})

    def run_subject(self, initial, final=None, **kwargs):
        final = initial if final is None else final
        with patch.object(
            subject.universe_loader, "load_universe", return_value=self.universe
        ) as load, patch.object(
            subject.universe_loader,
            "get_active_symbols",
            return_value=["A", "B", "C", "D"],
        ) as active, patch.object(
            subject.data_readiness,
            "build_data_readiness",
            side_effect=[initial, final],
        ) as build, patch.object(
            subject.data_readiness,
            "save_data_readiness",
            return_value=self.output,
        ) as save:
            result = subject.run_research_market_data(
                output_path=self.output, **kwargs
            )
        return result, load, active, build, save

    def test_inspect_mode_has_no_network_access(self):
        table = readiness_rows([("A", "missing"), ("B", "ready")])
        with patch.object(subject.update_data, "update_one_stock") as downloader:
            result, load, active, build, save = self.run_subject(table)
        downloader.assert_not_called()
        load.assert_called_once_with(None)
        active.assert_called_once_with(self.universe)
        self.assertEqual(build.call_count, 2)
        save.assert_called_once_with(table, output_path=self.output)
        self.assertFalse(result["download_enabled"])
        self.assertEqual(result["summary"]["attempted"], 0)

    def test_missing_candidates_only_preserve_active_order(self):
        table = readiness_rows(
            [("A", "ready"), ("B", "invalid"), ("C", "missing"), ("D", "insufficient")]
        )
        self.assertEqual(
            subject.select_download_candidates(table, ["D", "C", "B", "A"]),
            ["C"],
        )

    def test_limit_applies_to_missing_candidates(self):
        table = readiness_rows(
            [("A", "ready"), ("B", "missing"), ("C", "missing"), ("D", "missing")]
        )
        self.assertEqual(
            subject.select_download_candidates(
                table, ["A", "B", "C", "D"], limit=2
            ),
            ["B", "C"],
        )
        with self.assertRaisesRegex(ValueError, "positive integer"):
            subject.select_download_candidates(table, ["A"], limit=0)

    def test_failure_isolation_continues_to_later_symbols(self):
        initial = readiness_rows(
            [("A", "missing"), ("B", "missing"), ("C", "missing"), ("D", "ready")]
        )
        final = readiness_rows(
            [("A", "ready"), ("B", "missing"), ("C", "missing"), ("D", "ready")]
        )
        outcomes = [
            {"symbol": "A", "status": "success", "rows": 500},
            RuntimeError("timeout"),
            {"symbol": "C", "status": "failed", "message": "provider error"},
        ]
        with patch.object(
            subject.update_data, "update_one_stock", side_effect=outcomes
        ) as downloader:
            result, *_ = self.run_subject(initial, final, download=True)
        self.assertEqual(
            downloader.call_args_list, [call("A"), call("B"), call("C")]
        )
        self.assertEqual(
            [row["status"] for row in result["download_results"]],
            ["success", "failed", "failed"],
        )
        self.assertIn("RuntimeError", result["download_results"][1]["message"])
        self.assertEqual(result["summary"]["attempted"], 3)
        self.assertEqual(result["summary"]["failed"], 2)
        self.assertEqual(result["summary"]["final"]["ready"], 2)

    def test_download_uses_existing_downloader_with_limit(self):
        table = readiness_rows(
            [("A", "missing"), ("B", "missing"), ("C", "missing"), ("D", "ready")]
        )
        with patch.object(
            subject.update_data,
            "update_one_stock",
            return_value={"status": "empty", "rows": 0, "message": "no data"},
        ) as downloader:
            result, *_ = self.run_subject(table, download=True, limit=2)
        self.assertEqual(downloader.call_args_list, [call("A"), call("B")])
        self.assertEqual(result["candidates"], ["A", "B"])
        self.assertEqual(result["summary"]["empty"], 2)

    def test_malformed_downloader_result_is_isolated(self):
        table = readiness_rows([("A", "missing")])
        with patch.object(subject.update_data, "update_one_stock", return_value=None):
            result, *_ = self.run_subject(table, download=True)
        self.assertEqual(result["download_results"][0]["status"], "failed")
        self.assertIn("Malformed", result["download_results"][0]["message"])

    def test_production_pipeline_is_not_referenced(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "watchlist.csv",
            "universe_source",
            "load_active_universe(",
            "update_all_stocks(",
            "import run_all",
            "import portfolio",
            "import order",
            "import broker",
            "import backtest",
            "import yfinance",
        )
        for reference in forbidden_references:
            with self.subTest(reference=reference):
                self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
