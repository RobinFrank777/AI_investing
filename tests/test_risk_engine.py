import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import risk_engine


def price_history(closes):
    size = len(closes)
    return pd.DataFrame(
        {
            "Date": pd.date_range("2025-01-01", periods=size, freq="B"),
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * size,
        }
    )


class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_history(self, frame=None, name="NVDA.csv"):
        path = self.root / name
        source = price_history([100, 102, 101, 105, 103]) if frame is None else frame
        source.to_csv(path, index=False)
        return path

    def test_returns_fixed_single_row_and_infers_ticker(self):
        result = risk_engine.calculate_risk_metrics(self.write_history())
        self.assertEqual(len(result), 1)
        self.assertEqual(result.columns.tolist(), list(risk_engine.RISK_COLUMNS))
        self.assertEqual(result.at[0, "Ticker"], "NVDA")
        self.assertEqual(result.at[0, "RiskStatus"], "PASS")

    def test_explicit_ticker_is_supported(self):
        result = risk_engine.calculate_risk_metrics(
            self.write_history(name="history.csv"), ticker="MSFT"
        )
        self.assertEqual(result.at[0, "Ticker"], "MSFT")

    def test_annualized_volatility_matches_daily_sample_std(self):
        closes = pd.Series([100.0, 102.0, 101.0, 105.0, 103.0])
        result = risk_engine.calculate_risk_metrics(
            self.write_history(price_history(closes.tolist()))
        )
        expected = closes.pct_change().iloc[1:].std(ddof=1) * math.sqrt(252)
        self.assertAlmostEqual(result.at[0, "AnnualizedVolatility"], expected)

    def test_max_drawdown_is_negative_peak_to_trough_return(self):
        result = risk_engine.calculate_risk_metrics(
            self.write_history(price_history([100, 120, 90, 110]))
        )
        self.assertAlmostEqual(result.at[0, "MaxDrawdown"], -0.25)

    def test_sharpe_ratio_matches_zero_rate_annualized_formula(self):
        closes = pd.Series([100.0, 102.0, 101.0, 105.0, 103.0])
        returns = closes.pct_change().iloc[1:]
        expected = returns.mean() / returns.std(ddof=1) * math.sqrt(252)
        result = risk_engine.calculate_risk_metrics(
            self.write_history(price_history(closes.tolist()))
        )
        self.assertAlmostEqual(result.at[0, "SharpeRatio"], expected)

    def test_flat_prices_return_partial_without_crashing(self):
        result = risk_engine.calculate_risk_metrics(
            self.write_history(price_history([100, 100, 100, 100]))
        )
        self.assertEqual(result.at[0, "AnnualizedVolatility"], 0.0)
        self.assertEqual(result.at[0, "MaxDrawdown"], 0.0)
        self.assertTrue(pd.isna(result.at[0, "SharpeRatio"]))
        self.assertEqual(result.at[0, "RiskStatus"], "PARTIAL")

    def test_missing_file_returns_failed_row(self):
        result = risk_engine.calculate_risk_metrics(self.root / "MISSING.csv")
        self.assertEqual(result.at[0, "Ticker"], "MISSING")
        self.assertEqual(result.at[0, "RiskStatus"], "FAILED")
        self.assertIn("FileNotFoundError", result.at[0, "RiskError"])

    def test_empty_file_returns_failed_row(self):
        path = self.root / "EMPTY.csv"
        path.touch()
        result = risk_engine.calculate_risk_metrics(path)
        self.assertEqual(result.at[0, "RiskStatus"], "FAILED")
        self.assertIn("CSV is empty", result.at[0, "RiskError"])

    def test_missing_close_returns_failed_row(self):
        result = risk_engine.calculate_risk_metrics(
            self.write_history(price_history([1, 2, 3]).drop(columns=["Close"]))
        )
        self.assertEqual(result.at[0, "RiskStatus"], "FAILED")
        self.assertIn("Close column", result.at[0, "RiskError"])

    def test_dates_are_sorted_before_metrics(self):
        history = price_history([100, 120, 90, 110])
        history["Date"] = history["Date"].iloc[::-1].to_numpy()
        result = risk_engine.calculate_risk_metrics(self.write_history(history))
        sorted_close = pd.Series([110.0, 90.0, 120.0, 100.0])
        expected = (sorted_close / sorted_close.cummax() - 1).min()
        self.assertAlmostEqual(result.at[0, "MaxDrawdown"], expected)

    def test_no_universe_ranking_normalization_or_execution_dependencies(self):
        source = Path(risk_engine.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "universe_loader",
            "load_active_universe",
            "factor_ranking",
            "factor_normalization",
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
