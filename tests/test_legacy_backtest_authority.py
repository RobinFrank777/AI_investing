import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import backtest_engine
import portfolio_risk


def production_candidates():
    return pd.DataFrame(
        {
            "Ticker": ["AAA"],
            "RunId": ["candidate-20260812-test"],
            "AsOfDate": ["2026-08-12"],
            "CandidateRank": [1],
            "Eligibility": ["ELIGIBLE"],
            "FinalScore": [80.0],
            "TradeSignal": ["BUY"],
            "RS_Score": [75.0],
            "NearHighScore": [70.0],
            "Confidence": [0.9],
            "ScoreModelVersion": ["technical-score-v3.8.1-r1"],
            "UniverseVersion": ["test-universe"],
        }
    )


class LegacyBacktestAuthorityTests(unittest.TestCase):
    def run_default_portfolio(self, path):
        with patch.object(portfolio_risk, "PRODUCTION_CANDIDATE_OUTPUT", path):
            return portfolio_risk.build_model_portfolio()

    def test_legacy_backtest_is_explicitly_research_only(self):
        self.assertEqual(backtest_engine.BACKTEST_AUTHORITY, "RESEARCH_ONLY")
        self.assertIn(
            "NOT PRODUCTION BUY AUTHORITY",
            backtest_engine.BACKTEST_AUTHORITY_NOTICE,
        )

    def test_production_portfolio_has_no_legacy_backtest_authority_path(self):
        source = Path(portfolio_risk.__file__).read_text(encoding="utf-8")
        self.assertNotIn("backtest_qualified_20d.csv", source)
        self.assertNotIn("BACKTEST_QUALIFIED_20D_OUTPUT_PATH", source)

    def test_missing_production_candidates_fail_closed_without_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_default_portfolio(Path(root) / "missing.csv")
        self.assertTrue(result.empty)
        self.assertEqual(
            result.attrs["PortfolioStatus"],
            portfolio_risk.PRODUCTION_CANDIDATES_MISSING,
        )

    def test_empty_production_candidates_return_no_action(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "production_candidates.csv"
            production_candidates().iloc[:0].to_csv(path, index=False)
            result = self.run_default_portfolio(path)
        self.assertTrue(result.empty)
        self.assertEqual(
            result.attrs["PortfolioStatus"],
            portfolio_risk.PRODUCTION_CANDIDATES_EMPTY,
        )

    def test_incompatible_production_candidates_return_no_action(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "production_candidates.csv"
            pd.DataFrame({"Ticker": ["AAA"]}).to_csv(path, index=False)
            result = self.run_default_portfolio(path)
        self.assertTrue(result.empty)
        self.assertEqual(
            result.attrs["PortfolioStatus"],
            portfolio_risk.PRODUCTION_CANDIDATES_INCOMPATIBLE,
        )

    def test_stale_production_candidates_return_no_action(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "production_candidates.csv"
            data = production_candidates()
            data.loc[:, "AsOfDate"] = "2020-01-01"
            data.to_csv(path, index=False)
            result = self.run_default_portfolio(path)
        self.assertTrue(result.empty)
        self.assertEqual(
            result.attrs["PortfolioStatus"],
            portfolio_risk.PRODUCTION_CANDIDATES_STALE,
        )

    def test_valid_candidates_wait_for_production_risk_without_backtest(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "production_candidates.csv"
            production_candidates().to_csv(path, index=False)
            result = self.run_default_portfolio(path)
        self.assertTrue(result.empty)
        self.assertEqual(
            result.attrs["PortfolioStatus"],
            portfolio_risk.PRODUCTION_RISK_INPUTS_NOT_READY,
        )

    def test_injected_p1_policy_path_remains_available_for_contract_tests(self):
        injected = pd.DataFrame(
            {
                "Ticker": ["AAA"],
                "BacktestScore": [90.0],
                "AverageReturn": [0.1],
                "WinRate": [0.6],
                "MaxDrawdown": [-0.05],
                "SharpeRatio": [2.5],
            }
        )
        result = portfolio_risk.build_model_portfolio(injected)
        self.assertEqual(result.attrs["PortfolioStatus"], portfolio_risk.PORTFOLIO_READY)


if __name__ == "__main__":
    unittest.main()
