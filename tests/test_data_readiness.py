import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import config
import data_readiness
from universe_loader import REQUIRED_COLUMNS as UNIVERSE_COLUMNS


def universe_frame(symbols):
    rows = []
    for index, ticker in enumerate(symbols, start=1):
        rows.append({
            "order": index, "ticker": ticker, "company": f"Company {ticker}",
            "sector": "Technology", "industry": "Software", "theme": "Research",
            "layer": "A", "priority": index, "status": "ACTIVE",
            "asset_type": "Equity", "notes": "",
        })
    return pd.DataFrame(rows, columns=UNIVERSE_COLUMNS)


def price_frame(rows=252):
    values = pd.Series(range(rows), dtype=float) + 100.0
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=rows, freq="B"),
        "Open": values,
        "High": values + 2,
        "Low": values - 1,
        "Close": values + 1,
        "Volume": [1_000_000] * rows,
    })


class DataReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()

    def write_universe(self, symbols):
        path = self.root / "universe.csv"
        universe_frame(symbols).to_csv(path, index=False)
        return path

    def write_prices(self, ticker, frame):
        path = self.data_dir / f"{ticker}.csv"
        frame.to_csv(path, index=False)
        return path

    def audit(self, symbols):
        return data_readiness.build_data_readiness(self.write_universe(symbols), self.data_dir)

    def test_valid_canonical_data_is_ready_and_versioned(self):
        self.write_prices("GOOD", price_frame())
        row = self.audit(["GOOD"]).iloc[0]
        self.assertTrue(row["Ready"])
        self.assertEqual(row["Reason"], "READY")
        self.assertEqual(row["UniverseVersion"], config.PRIMARY_UNIVERSE_VERSION)
        self.assertEqual((row["Rows"], row["FirstDate"], row["LastDate"]), (252, "2024-01-01", "2024-12-17"))

    def test_missing_file_is_not_ready_without_replacement(self):
        result = self.audit(["MISSING", "ALSO_MISSING"])
        self.assertEqual(result["Ticker"].tolist(), ["MISSING", "ALSO_MISSING"])
        self.assertEqual(result["Reason"].tolist(), ["MISSING_FILE", "MISSING_FILE"])
        self.assertFalse(result["Ready"].any())

    def test_duplicate_dates_are_not_ready(self):
        frame = price_frame()
        frame.loc[1, "Date"] = frame.loc[0, "Date"]
        self.write_prices("DUP", frame)
        row = self.audit(["DUP"]).iloc[0]
        self.assertFalse(row["Ready"])
        self.assertEqual(row["DuplicateDates"], 1)
        self.assertIn("DUPLICATE_DATES", row["Reason"])

    def test_invalid_numeric_is_not_ready(self):
        frame = price_frame()
        frame["Close"] = frame["Close"].astype(object)
        frame.loc[2, "Close"] = "bad"
        self.write_prices("NUM", frame)
        row = self.audit(["NUM"]).iloc[0]
        self.assertEqual(row["InvalidNumeric"], 1)
        self.assertIn("INVALID_NUMERIC", row["Reason"])

    def test_invalid_ohlc_is_not_ready(self):
        frame = price_frame()
        frame.loc[2, "High"] = 1.0
        self.write_prices("OHLC", frame)
        row = self.audit(["OHLC"]).iloc[0]
        self.assertEqual(row["InvalidOHLC"], 1)
        self.assertIn("INVALID_OHLC", row["Reason"])

    def test_insufficient_history_is_not_ready(self):
        self.write_prices("SHORT", price_frame(251))
        row = self.audit(["SHORT"]).iloc[0]
        self.assertFalse(row["MinimumHistoryPass"])
        self.assertIn("INSUFFICIENT_HISTORY", row["Reason"])

    def test_symbol_behind_universe_latest_date_is_explicitly_stale(self):
        old = price_frame(); new = price_frame()
        new["Date"] = pd.to_datetime(new["Date"]) + pd.Timedelta(days=1)
        self.write_prices("OLD", old); self.write_prices("NEW", new)
        result = self.audit(["OLD", "NEW"])
        stale = result.set_index("Ticker").loc["OLD"]
        self.assertFalse(stale["Ready"])
        self.assertEqual(stale["Reason"], "STALE_MARKET_DATA")
        self.assertEqual(data_readiness.readiness_summary(result)["stale_market_data"], 1)

    def test_provider_rejection_is_distinct_and_preserves_latest_accepted_date(self):
        self.write_prices("REJECT", price_frame())
        required = pd.Timestamp("2024-12-18")
        result = data_readiness.build_data_readiness(
            self.write_universe(["REJECT"]), self.data_dir,
            required_as_of=required,
            refresh_results={"REJECT": {
                "status": "provider_rejected", "rejected_dates": ["2024-12-18"],
            }},
        )
        row = result.iloc[0]
        self.assertFalse(row["Ready"])
        self.assertEqual(row["Status"], "PROVIDER_REJECTED")
        self.assertEqual(row["Reason"], "PROVIDER_REJECTED_CURRENT_SESSION")
        self.assertEqual(row["LatestAcceptedDate"], "2024-12-17")
        self.assertEqual(row["ProviderRejectedDate"], "2024-12-18")

    def test_partial_readiness_counts_and_full_universe_version_are_preserved(self):
        symbols = [f"READY{i:03d}" for i in range(143)] + ["SHORT1", "SHORT2"] + [f"REJECT{i}" for i in range(5)]
        base = price_frame()
        current = base.copy()
        current["Date"] = pd.to_datetime(current["Date"]) + pd.Timedelta(days=1)
        for ticker in symbols[:143]:
            self.write_prices(ticker, current)
        for ticker in symbols[143:145]:
            self.write_prices(ticker, price_frame(20))
        for ticker in symbols[145:]:
            self.write_prices(ticker, base)
        required = pd.Timestamp("2024-12-18")
        refresh = {
            ticker: {"status": "provider_rejected", "rejected_dates": ["2024-12-18"]}
            for ticker in symbols[145:]
        }
        result = data_readiness.build_data_readiness(
            self.write_universe(symbols), self.data_dir,
            required_as_of=required, refresh_results=refresh,
        )
        self.assertEqual(len(result), 150)
        self.assertEqual(int(result["Ready"].sum()), 143)
        self.assertEqual(result["Status"].value_counts().to_dict(), {
            "READY": 143, "PROVIDER_REJECTED": 5, "INSUFFICIENT_HISTORY": 2,
        })
        self.assertEqual(result["UniverseVersion"].nunique(), 1)
        self.assertEqual(result["UniverseVersion"].iloc[0], config.PRIMARY_UNIVERSE_VERSION)

    def test_one_failure_does_not_reduce_configured_count(self):
        self.write_prices("GOOD", price_frame())
        result = self.audit(["GOOD", "MISSING"])
        summary = data_readiness.readiness_summary(result)
        self.assertEqual(summary["configured"], 2)
        self.assertEqual((summary["ready"], summary["not_ready"]), (1, 1))

    def test_empty_file_fails_safely(self):
        (self.data_dir / "EMPTY.csv").touch()
        row = self.audit(["EMPTY"]).iloc[0]
        self.assertEqual(row["Reason"], "PARSE_ERROR")
        self.assertIn("empty", row["ParseError"])

    def test_parse_exception_does_not_abort_batch(self):
        self.write_prices("BAD", price_frame())
        self.write_prices("GOOD", price_frame())
        real_read_csv = pd.read_csv

        def read_csv(path, *args, **kwargs):
            if str(path).endswith("BAD.csv"):
                raise pd.errors.ParserError("broken")
            return real_read_csv(path, *args, **kwargs)

        with patch("data_readiness.pd.read_csv", side_effect=read_csv):
            result = self.audit(["BAD", "GOOD"])
        self.assertEqual(result["Reason"].tolist(), ["PARSE_ERROR", "READY"])

    def test_default_audit_uses_primary_universe(self):
        universe = universe_frame(["PRIMARY"])
        self.write_prices("PRIMARY", price_frame())
        with patch("data_readiness.load_universe", return_value=universe) as loader:
            result = data_readiness.build_data_readiness(data_dir=self.data_dir)
        loader.assert_called_once_with(config.PRIMARY_UNIVERSE_PATH)
        self.assertEqual(result["Ticker"].tolist(), ["PRIMARY"])

    def test_audit_does_not_modify_universe_and_output_schema_is_stable(self):
        universe_path = self.write_universe(["GOOD"])
        self.write_prices("GOOD", price_frame())
        before = universe_path.read_bytes()
        output = self.root / "results" / "quality.csv"
        result = data_readiness.run_data_readiness(universe_path, self.data_dir, output)
        self.assertEqual(universe_path.read_bytes(), before)
        saved = pd.read_csv(output)
        self.assertEqual(saved.columns.tolist(), list(data_readiness.READINESS_COLUMNS))
        self.assertEqual(len(saved), 1)
        self.assertEqual(result["summary"]["configured"], 1)


if __name__ == "__main__":
    unittest.main()
