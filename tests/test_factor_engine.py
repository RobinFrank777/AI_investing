import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_engine
from price_factors import calculate_price_factors


def price_history(rows=60):
    return pd.DataFrame(
        {
            "Date": pd.date_range("2025-01-01", periods=rows, freq="B"),
            "Open": range(100, 100 + rows),
            "High": range(101, 101 + rows),
            "Low": range(99, 99 + rows),
            "Close": range(100, 100 + rows),
            "Volume": [1_000_000] * rows,
        }
    )


class FactorEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_history(self, frame=None, name="NVDA.csv"):
        path = self.root / name
        (price_history() if frame is None else frame).to_csv(path, index=False)
        return path

    def test_returns_one_row_with_fixed_columns(self):
        result = factor_engine.calculate_factors(self.write_history())
        self.assertEqual(len(result), 1)
        self.assertEqual(result.columns.tolist(), list(factor_engine.FACTOR_ENGINE_COLUMNS))
        self.assertEqual(result.iloc[0]["Ticker"], "NVDA")

    def test_values_match_existing_price_factor_formulas(self):
        history = price_history()
        expected = calculate_price_factors(history)
        result = factor_engine.calculate_factors(self.write_history(history)).iloc[0]
        for column, value in expected.items():
            self.assertAlmostEqual(result[column], value)

    def test_explicit_ticker_is_supported(self):
        result = factor_engine.calculate_factors(
            self.write_history(name="history.csv"), ticker="MSFT"
        )
        self.assertEqual(result.at[0, "Ticker"], "MSFT")

    def test_insufficient_history_preserves_missing_factor(self):
        result = factor_engine.calculate_factors(
            self.write_history(price_history(20))
        )
        self.assertTrue(pd.isna(result.at[0, "TrendValue"]))
        self.assertTrue(pd.isna(result.at[0, "MomentumValue"]))
        self.assertTrue(pd.isna(result.at[0, "Volatility20D"]))

    def test_missing_file_has_clear_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "Historical price CSV not found"):
            factor_engine.calculate_factors(self.root / "missing.csv")

    def test_empty_file_is_rejected(self):
        path = self.root / "empty.csv"
        path.touch()
        with self.assertRaisesRegex(ValueError, "CSV is empty"):
            factor_engine.calculate_factors(path)

    def test_header_only_file_is_rejected(self):
        path = self.write_history(price_history(0))
        with self.assertRaisesRegex(ValueError, "contains no rows"):
            factor_engine.calculate_factors(path)

    def test_missing_close_column_is_rejected_by_existing_formula(self):
        path = self.write_history(price_history().drop(columns=["Close"]))
        with self.assertRaisesRegex(ValueError, "Close column"):
            factor_engine.calculate_factors(path)

    def test_existing_factor_wrapper_is_called_once(self):
        expected = {
            "TrendValue": 0.1,
            "MomentumValue": 0.2,
            "Volatility20D": 0.3,
        }
        with patch.object(
            factor_engine, "calculate_price_factors", return_value=expected
        ) as calculate:
            result = factor_engine.calculate_factors(self.write_history())
        calculate.assert_called_once()
        self.assertEqual(result.iloc[0].to_dict(), {"Ticker": "NVDA", **expected})

    def test_no_universe_ranking_or_trading_dependencies(self):
        source = Path(factor_engine.__file__).read_text(encoding="utf-8")
        forbidden = (
            "universe_loader",
            "universe_source",
            "watchlist",
            "factor_normalization",
            "factor_composite",
            "portfolio",
            "order",
            "broker",
            "backtest",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertNotIn(f"import {name}", source)


if __name__ == "__main__":
    unittest.main()
