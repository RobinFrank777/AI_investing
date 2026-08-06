import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_snapshot as snapshot


def market(rows=60):
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=rows),
        "Close": range(100, 100 + rows),
        "High": range(101, 101 + rows),
        "Low": range(99, 99 + rows),
        "Volume": [1000] * rows,
    })


def sources(ticker="AAPL", complete=True):
    values = {
        "Return20D": .1, "TechnicalScore": 70, "BacktestScore": 80,
        "CombinedScore": 77, "MaxDrawdown": -.1, "SharpeRatio": 1.5,
    }
    if not complete:
        values.pop("CombinedScore")
    return {
        "technical": {"rows": {ticker: {k: values[k] for k in ("Return20D", "TechnicalScore")}}, "duplicates": set()},
        "backtest": {"rows": {ticker: {k: values[k] for k in ("BacktestScore", "MaxDrawdown", "SharpeRatio")}}, "duplicates": set()},
        "combined": {"rows": {ticker: ({"CombinedScore": values["CombinedScore"]} if "CombinedScore" in values else {})}, "duplicates": set()},
    }


class FactorSnapshotTests(unittest.TestCase):
    def build(self, symbol="AAPL", data=None, source_data=None):
        with patch("factor_snapshot._load_optional_sources", return_value=(
            sources() if source_data is None else source_data
        )):
            return snapshot.build_factor_snapshot(
                symbol, market() if data is None else data
            )

    def test_valid_data_identification(self):
        row = self.build()
        self.assertEqual((row["Ticker"], row["DataRows"]), ("AAPL", 60))

    def test_latest_date(self):
        self.assertEqual(self.build()["AsOfDate"], "2024-02-29")

    def test_latest_close(self):
        self.assertEqual(self.build()["Close"], 159)

    def test_input_not_mutated(self):
        data = market(); before = data.copy(deep=True); self.build(data=data)
        pd.testing.assert_frame_equal(data, before)

    def test_lowercase_symbol_normalized(self):
        self.assertEqual(self.build(" aapl ")["Ticker"], "AAPL")

    @patch("factor_snapshot.load_stock", side_effect=FileNotFoundError)
    def test_missing_file_failed(self, _):
        self.assertEqual(snapshot.build_factor_snapshot("AAPL")["FactorStatus"], "FAILED")

    def test_empty_data_failed(self):
        self.assertEqual(self.build(data=pd.DataFrame())["FactorStatus"], "FAILED")

    def test_missing_date_failed(self):
        self.assertIn("Date", self.build(data=pd.DataFrame({"Close": [1]}))["FactorMessage"])

    def test_missing_close_failed(self):
        self.assertIn("Close", self.build(data=pd.DataFrame({"Date": ["2024-01-01"]}))["FactorMessage"])

    def test_invalid_dates_failed(self):
        row = self.build(data=pd.DataFrame({"Date": ["bad"], "Close": [1]}))
        self.assertEqual(row["FactorStatus"], "FAILED")

    def test_insufficient_history_documented(self):
        row = self.build(data=market(59))
        self.assertIn("60 required", row["FactorMessage"])

    def test_technical_factor_preserved(self):
        self.assertEqual(self.build()["TechnicalScore"], 70)

    def test_missing_optional_is_partial(self):
        self.assertEqual(self.build(source_data=sources(complete=False))["FactorStatus"], "PARTIAL")

    def test_missing_optional_listed(self):
        self.assertIn("CombinedScore", self.build(source_data=sources(complete=False))["MissingFactors"])

    def test_no_missing_optional_is_empty(self):
        self.assertEqual(self.build()["MissingFactors"], "")

    def test_missing_optional_files_do_not_crash(self):
        empty = {name: {"rows": {}, "duplicates": set()} for name in ("technical", "backtest", "combined")}
        self.assertEqual(self.build(source_data=empty)["FactorStatus"], "PARTIAL")

    def test_duplicate_source_explicit(self):
        data = sources(); data["combined"] = {"rows": {}, "duplicates": {"AAPL"}}
        self.assertIn("Duplicate ticker", self.build(source_data=data)["FactorMessage"])

    def test_unknown_source_ticker_not_position_matched(self):
        self.assertIsNone(self.build("MSFT", source_data=sources())["CombinedScore"])

    @patch("factor_snapshot._load_optional_sources", return_value=sources())
    @patch("factor_snapshot.load_stock", return_value=market())
    @patch("factor_snapshot.load_active_universe", return_value=["MSFT", "AAPL"])
    def test_universe_loaded_once(self, active, *_):
        snapshot.build_factor_snapshot_table(); active.assert_called_once_with()

    @patch("factor_snapshot.load_active_universe")
    @patch("factor_snapshot.load_stock", return_value=market())
    def test_explicit_symbols_override_universe(self, _, active):
        snapshot.build_factor_snapshot_table(["AAPL"]); active.assert_not_called()

    @patch("factor_snapshot._load_optional_sources", return_value=sources())
    @patch("factor_snapshot.load_stock", return_value=market())
    def test_order_preserved(self, *_):
        table = snapshot.build_factor_snapshot_table(["MSFT", "AAPL"])
        self.assertEqual(table.Ticker.tolist(), ["MSFT", "AAPL"])

    @patch("factor_snapshot._load_optional_sources", return_value=sources())
    @patch("factor_snapshot.load_stock", side_effect=[FileNotFoundError(), market()])
    def test_failed_symbol_does_not_stop(self, *_):
        table = snapshot.build_factor_snapshot_table(["BAD", "AAPL"])
        self.assertEqual(table.FactorStatus.tolist(), ["FAILED", "PASS"])

    @patch("factor_snapshot._load_optional_sources", return_value=sources())
    @patch("factor_snapshot.load_stock", return_value=market())
    def test_one_row_per_request(self, *_):
        self.assertEqual(len(snapshot.build_factor_snapshot_table(["AAPL", "AAPL"])), 2)

    @patch("factor_snapshot._load_optional_sources", return_value=sources())
    @patch("factor_snapshot.load_stock", return_value=market())
    def test_repeated_calls_deterministic(self, *_):
        a = snapshot.build_factor_snapshot_table(["AAPL"]); b = snapshot.build_factor_snapshot_table(["AAPL"])
        pd.testing.assert_frame_equal(a, b)

    @patch("factor_snapshot._load_optional_sources", return_value=sources())
    @patch("factor_snapshot.load_stock", return_value=market())
    def test_fixed_column_order(self, *_):
        self.assertEqual(list(snapshot.build_factor_snapshot_table(["AAPL"])), snapshot.SNAPSHOT_COLUMNS)

    def test_native_factor_columns_follow_return(self):
        start = snapshot.SNAPSHOT_COLUMNS.index("Return20D")
        self.assertEqual(snapshot.SNAPSHOT_COLUMNS[start:start + 4], ["Return20D", "TrendValue", "MomentumValue", "Volatility20D"])

    def test_full_history_produces_native_factors(self):
        row = self.build()
        for factor in ("TrendValue", "MomentumValue", "Volatility20D"):
            self.assertIsNotNone(row[factor])

    def test_short_history_native_factors_missing_and_partial(self):
        row = self.build(data=market(20))
        self.assertEqual(row["FactorStatus"], "PARTIAL")
        self.assertIn("TrendValue;MomentumValue;Volatility20D", row["MissingFactors"])

    @patch("factor_snapshot.calculate_price_factors", side_effect=RuntimeError("bad factors"))
    def test_native_exception_is_symbol_level(self, _):
        row = self.build()
        self.assertEqual(row["FactorStatus"], "PARTIAL")
        self.assertIn("bad factors", row["FactorMessage"])

    @patch("factor_snapshot.load_stock", return_value=market())
    def test_single_snapshot_loads_market_data_once(self, loader):
        with patch("factor_snapshot._load_optional_sources", return_value=sources()):
            snapshot.build_factor_snapshot("AAPL")
        loader.assert_called_once_with("AAPL")

    @patch("factor_snapshot._load_optional_sources")
    def test_runtime_sources_disabled_are_not_opened(self, loader):
        row = snapshot.build_factor_snapshot(
            "AAPL", market(), include_runtime_sources=False
        )
        loader.assert_not_called()
        self.assertIsNotNone(row["TrendValue"])
        self.assertIsNone(row["TechnicalScore"])

    @patch("factor_snapshot._load_optional_sources")
    @patch("factor_snapshot.load_stock", return_value=market())
    def test_table_forwards_runtime_source_option(self, _, loader):
        snapshot.build_factor_snapshot_table(
            ["AAPL"], include_runtime_sources=False
        )
        loader.assert_not_called()

    @patch("factor_snapshot.build_factor_snapshot_table", return_value=pd.DataFrame([{"Ticker": "AAPL"}]))
    def test_save_forwards_runtime_source_option(self, table):
        with tempfile.TemporaryDirectory() as directory:
            snapshot.save_factor_snapshot(
                ["AAPL"], Path(directory) / "out.csv",
                include_runtime_sources=False,
            )
        table.assert_called_once_with(
            ["AAPL"], include_runtime_sources=False
        )

    def test_source_loader_missing_file(self):
        with patch.object(snapshot, "SOURCE_SPECS", (("technical", Path("/missing"), {}),)):
            self.assertEqual(snapshot._load_optional_sources()["technical"]["rows"], {})

    def test_source_loader_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.csv"; pd.DataFrame({"Ticker": ["aapl", " AAPL "], "Score": [1, 2]}).to_csv(path, index=False)
            with patch.object(snapshot, "SOURCE_SPECS", (("technical", path, {"Score": "TechnicalScore"}),)):
                self.assertEqual(snapshot._load_optional_sources()["technical"]["duplicates"], {"AAPL"})

    @patch("factor_snapshot.build_factor_snapshot_table", return_value=pd.DataFrame([{"Ticker": "AAPL"}]))
    def test_output_directory_created(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "out.csv"; snapshot.save_factor_snapshot([], path)
            self.assertTrue(path.parent.is_dir())

    @patch("factor_snapshot.build_factor_snapshot_table", return_value=pd.DataFrame([{"Ticker": "AAPL"}]))
    def test_csv_exists_and_nonempty(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = snapshot.save_factor_snapshot([], Path(directory) / "out.csv")
            self.assertGreater(path.stat().st_size, 0)

    @patch("factor_snapshot.build_factor_snapshot_table", return_value=pd.DataFrame([{"Ticker": "AAPL"}]))
    def test_csv_has_no_index(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = snapshot.save_factor_snapshot([], Path(directory) / "out.csv")
            self.assertEqual(list(pd.read_csv(path)), ["Ticker"])

    @patch("factor_snapshot.build_factor_snapshot_table", return_value=pd.DataFrame([{"Ticker": "AAPL"}]))
    def test_explicit_output_honored(self, _):
        with tempfile.TemporaryDirectory() as directory:
            wanted = Path(directory) / "wanted.csv"
            self.assertEqual(snapshot.save_factor_snapshot([], wanted), wanted)

    @patch("factor_snapshot.save_factor_snapshot")
    def test_cli_default_invokes_save(self, save):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.csv"; pd.DataFrame({"FactorStatus": ["PASS"]}).to_csv(path, index=False); save.return_value = path
            self.assertEqual(snapshot.main([]), 0); save.assert_called_once_with(None, None)

    @patch("factor_snapshot.save_factor_snapshot")
    def test_cli_symbol_limits_output(self, save):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.csv"; pd.DataFrame({"FactorStatus": ["PASS"]}).to_csv(path, index=False); save.return_value = path
            snapshot.main(["--symbol", "AAPL"]); self.assertEqual(save.call_args.args[0], ["AAPL"])

    def test_cli_invalid_arguments_nonzero(self):
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()): snapshot.main(["--bad"])
        self.assertNotEqual(raised.exception.code, 0)

    @patch("factor_snapshot.save_factor_snapshot", side_effect=FileNotFoundError("missing"))
    def test_expected_cli_error_has_no_traceback(self, _):
        output = io.StringIO()
        with contextlib.redirect_stderr(output): self.assertEqual(snapshot.main([]), 1)
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
