import tempfile
import unittest
import inspect
from pathlib import Path

import numpy as np
import pandas as pd

from config import PRIMARY_UNIVERSE_VERSION
import portfolio_risk_calculator as subject


def candidate(rows=None):
    rows = rows or [("AAA", True)]
    count = len(rows)
    return pd.DataFrame({
        "Ticker": [row[0] for row in rows], "RunId": ["run-1"] * count,
        "AsOfDate": ["2026-06-30"] * count,
        "UniverseVersion": [PRIMARY_UNIVERSE_VERSION] * count,
        "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * count,
        "CandidateRank": range(1, count + 1), "FinalScore": [80.0] * count,
        "TradeSignal": ["BUY" if row[1] else "WATCH" for row in rows],
        "Eligibility": ["ELIGIBLE" if row[1] else "INELIGIBLE" for row in rows],
        "PortfolioEligible": [row[1] for row in rows],
    })


def market(periods=90, end="2026-06-30"):
    dates = pd.bdate_range(end=pd.Timestamp(end), periods=periods)
    increments = np.resize(np.array([0.4, 0.7, -0.2, 0.5, 0.1]), periods)
    close = 100 + np.cumsum(increments)
    return pd.DataFrame({
        "Date": dates, "High": close * 1.01, "Low": close * .99,
        "Close": close, "Volume": np.linspace(1_000_000, 1_200_000, periods),
    })


class PortfolioRiskCalculatorTests(unittest.TestCase):
    def calculate(self, candidates=None, data=None):
        source = candidate() if candidates is None else candidates
        prices = {ticker: market() for ticker in source.Ticker}
        if data is not None:
            prices[source.Ticker.iloc[0]] = data
        return subject.calculate_portfolio_risk_inputs(
            source, market_data=prices,
            calculation_timestamp="2026-06-30T22:00:00+00:00",
        )

    def test_valid_production_risk_contract(self):
        result = self.calculate()
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(result.at[0, "RiskStatus"], "RISK_READY")
        self.assertTrue(bool(result.at[0, "RiskReadyForPortfolio"]))
        self.assertEqual(result.attrs["RiskBuildStatus"], subject.RISK_INPUTS_READY)
        self.assertEqual(result.at[0, "RiskModelVersion"], subject.RISK_MODEL_VERSION)
        self.assertEqual(result.at[0, "LatestCloseAsOf"], "2026-06-30")
        self.assertLessEqual(result.at[0, "LatestCloseAsOf"], result.at[0, "AsOfDate"])
        self.assertTrue(np.isfinite(result.loc[0, ["MaxDrawdown", "SharpeRatio", "Volatility60D"]].astype(float)).all())

    def test_multiple_and_partial_ready_candidates(self):
        data = candidate([("AAA", True), ("BBB", True)])
        result = subject.calculate_portfolio_risk_inputs(
            data, market_data={"AAA": market(), "BBB": market(20)},
            calculation_timestamp="2026-06-30T22:00:00+00:00",
        )
        self.assertEqual(result.RiskStatus.tolist(), ["RISK_READY", "INSUFFICIENT_HISTORY"])
        self.assertEqual(result.RiskReadyForPortfolio.tolist(), [True, False])

    def test_all_risk_unavailable_is_stable(self):
        result = self.calculate(data=market(20))
        self.assertEqual(result.attrs["RiskBuildStatus"], subject.NO_RISK_READY_CANDIDATES)
        self.assertFalse(result.RiskReadyForPortfolio.any())

    def test_future_price_mutation_and_append_are_isolated(self):
        original = market()
        future = pd.DataFrame({"Date": pd.bdate_range("2026-07-01", periods=5),
                               "High": 999, "Low": 1, "Close": 500, "Volume": 9_000_000})
        appended = pd.concat([original, future], ignore_index=True)
        changed = appended.copy(); changed.loc[changed.Date > pd.Timestamp("2026-06-30"), "Close"] = np.inf
        pd.testing.assert_frame_equal(self.calculate(data=original), self.calculate(data=appended))
        pd.testing.assert_frame_equal(self.calculate(data=original), self.calculate(data=changed))

    def test_mixed_metadata_is_rejected(self):
        for column, value in (("RunId", "run-2"), ("AsOfDate", "2026-06-29"),
                              ("UniverseVersion", "other"), ("ScoreModelVersion", "other")):
            data = candidate([("AAA", True), ("BBB", True)]); data.loc[1, column] = value
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "mixed " + column):
                subject.calculate_portfolio_risk_inputs(data)

    def test_missing_and_mismatched_universe_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "UniverseVersion"):
            subject.calculate_portfolio_risk_inputs(candidate().drop(columns=["UniverseVersion"]))
        data = candidate(); data.loc[:, "UniverseVersion"] = "other"
        with self.assertRaisesRegex(ValueError, "incompatible UniverseVersion"):
            subject.calculate_portfolio_risk_inputs(data)

    def test_metadata_and_score_alias_are_preserved(self):
        result = self.calculate()
        for column in ("RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion"):
            self.assertEqual(result.at[0, column], candidate().at[0, column])
        self.assertEqual(result.at[0, "BacktestScore"], result.at[0, "FinalScore"])
        self.assertEqual(result.at[0, "BacktestScoreSemantic"], "COMPATIBILITY_ALIAS_ONLY")
        self.assertTrue(pd.isna(result.at[0, "AverageReturn"]))
        self.assertTrue(pd.isna(result.at[0, "WinRate"]))

    def test_zero_eligible_is_no_action_with_stable_schema(self):
        result = self.calculate(candidates=candidate([("AAA", False)]))
        self.assertTrue(result.empty)
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(result.attrs["RiskBuildStatus"], subject.NO_PORTFOLIO_ELIGIBLE_CANDIDATES)

    def test_insufficient_stale_invalid_and_zero_volatility(self):
        cases = []
        cases.append((market(20), "INSUFFICIENT_HISTORY"))
        cases.append((market(end="2026-06-20"), "STALE_HISTORY"))
        invalid = market(); invalid.loc[2, "Close"] = np.inf
        cases.append((invalid, "INVALID_RISK_METRIC"))
        flat = market(); flat.loc[:, "Close"] = 100; flat.loc[:, "High"] = 101; flat.loc[:, "Low"] = 99
        cases.append((flat, "INVALID_RISK_METRIC"))
        for data, status in cases:
            with self.subTest(status=status):
                result = self.calculate(data=data)
                self.assertEqual(result.at[0, "RiskStatus"], status)
                self.assertFalse(bool(result.at[0, "RiskReadyForPortfolio"]))
                self.assertEqual(result.at[0, "RiskLevel"], "Unknown")
                self.assertEqual(result.at[0, "RiskWeightMultiplier"], 0)

    def test_risk_model_version_is_deterministic(self):
        self.assertEqual(subject.RISK_MODEL_VERSION, "risk-model-v3.8.2-p2")
        self.assertEqual(self.calculate().RiskModelVersion.unique().tolist(), [subject.RISK_MODEL_VERSION])

    def test_builder_reads_candidate_authority_and_writes_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "production_candidates.csv"; output = root / "risk.csv"
            raw = candidate([("AAA", False)]).drop(columns=["PortfolioEligible"])
            raw.to_csv(source, index=False); before = source.read_bytes()
            result, saved = subject.build_production_risk_inputs(input_path=source, output_path=output)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(saved, output)
            self.assertTrue(result.empty)
            self.assertEqual(tuple(pd.read_csv(output).columns), subject.OUTPUT_COLUMNS)

    def test_2026_06_18_buy_day_replay_contract(self):
        tickers = ["SNDK", "ARM", "MU", "WDC", "MRVL", "STX", "INTC", "NBIS"]
        data = candidate([(ticker, True) for ticker in tickers])
        data.loc[:, "AsOfDate"] = "2026-06-18"
        prices = {ticker: market(end="2026-06-18") for ticker in tickers}
        result = subject.calculate_portfolio_risk_inputs(
            data, market_data=prices,
            calculation_timestamp="2026-06-18T22:00:00+00:00",
        )
        self.assertEqual(len(result), 8)
        self.assertTrue(result.RiskReadyForPortfolio.all())
        self.assertTrue((result.LatestCloseAsOf <= result.AsOfDate).all())

    def test_builder_has_no_legacy_or_allocation_dependency(self):
        source = inspect.getsource(subject)
        self.assertNotIn("backtest_qualified_20d.csv", source)
        self.assertNotIn("production_backtest", source)
        self.assertNotIn("backtest_engine", source)
        self.assertNotIn("build_model_portfolio", source)


if __name__ == "__main__":
    unittest.main()
