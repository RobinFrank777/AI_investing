import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import portfolio_risk_calculator as subject


def candidate(rows=None):
    rows = rows or [("AAA", True)]
    return pd.DataFrame({
        "Ticker": [row[0] for row in rows], "RunId": ["run-1"] * len(rows),
        "AsOfDate": ["2026-06-30"] * len(rows),
        "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * len(rows),
        "FinalScore": [80.0] * len(rows), "TradeSignal": ["BUY"] * len(rows),
        "PortfolioEligible": [row[1] for row in rows],
    })


def snapshot(tickers=("AAA",)):
    return pd.DataFrame({
        "Ticker": list(tickers), "RunId": ["run-1"] * len(tickers),
        "AsOfDate": ["2026-06-30"] * len(tickers),
        "PortfolioSnapshotId": ["portfolio-1"] * len(tickers),
        "PortfolioAsOfDate": ["2026-06-30"] * len(tickers),
        "CurrentPortfolioWeight": [0.0] * len(tickers),
    })


def market(periods=90):
    dates = pd.bdate_range("2026-03-02", periods=periods)
    close = np.linspace(100, 140, periods)
    return pd.DataFrame({
        "Date": dates, "Open": close, "High": close * 1.01,
        "Low": close * .99, "Close": close,
        "Volume": np.linspace(1_000_000, 1_200_000, periods),
    })


class PortfolioRiskCalculatorTests(unittest.TestCase):
    def calculate(self, candidates=None, data=None, portfolio=None):
        return subject.calculate_portfolio_risk_inputs(
            candidate() if candidates is None else candidates,
            market_data={"AAA": market() if data is None else data},
            portfolio_snapshot=snapshot() if portfolio is None else portfolio,
            calculation_timestamp="2026-06-30T22:00:00+00:00",
        )

    def test_valid_point_in_time_risk_contract(self):
        result = self.calculate()
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(result.at[0, "RiskValidationStatus"], "PASS")
        self.assertEqual(result.at[0, "RiskStatus"], "READY")
        self.assertEqual(result.at[0, "RiskModelVersion"], subject.RISK_MODEL_VERSION)
        self.assertEqual(result.at[0, "ObservationEndDate"], "2026-06-30")
        self.assertTrue(np.isfinite(result.loc[0, ["Volatility20D", "Volatility60D", "TrailingDrawdown", "ATR14", "AverageVolume20D", "AverageDollarVolume20D"]].astype(float)).all())

    def test_future_price_mutation_is_isolated(self):
        original = market(110)
        changed = original.copy(deep=True)
        future = pd.to_datetime(changed.Date) > pd.Timestamp("2026-06-30")
        changed.loc[future, ["Open", "High", "Low", "Close", "Volume"]] = float("inf")
        pd.testing.assert_frame_equal(self.calculate(data=original), self.calculate(data=changed))

    def test_future_row_append_is_isolated(self):
        original = market(90)
        future_dates = pd.bdate_range(pd.Timestamp(original.Date.iloc[-1]) + pd.Timedelta(days=1), periods=20)
        future = pd.DataFrame({"Date": future_dates, "Open": 500, "High": 510, "Low": 490, "Close": 500, "Volume": 9_000_000})
        pd.testing.assert_frame_equal(self.calculate(data=original), self.calculate(data=pd.concat([original, future], ignore_index=True)))

    def test_mixed_as_of_date_is_rejected(self):
        data = candidate([("AAA", True), ("BBB", True)]); data.loc[1, "AsOfDate"] = "2026-06-29"
        with self.assertRaisesRegex(ValueError, "mixed AsOfDate"):
            subject.calculate_portfolio_risk_inputs(data)

    def test_mixed_run_id_is_rejected(self):
        data = candidate([("AAA", True), ("BBB", True)]); data.loc[1, "RunId"] = "run-2"
        with self.assertRaisesRegex(ValueError, "mixed RunId"):
            subject.calculate_portfolio_risk_inputs(data)

    def test_duplicate_normalized_ticker_is_rejected(self):
        data = candidate([("AAA", True), (" aaa ", True)])
        with self.assertRaisesRegex(ValueError, "duplicate ticker"):
            subject.calculate_portfolio_risk_inputs(data)

    def test_non_finite_candidate_score_is_rejected(self):
        for value in (float("nan"), float("inf")):
            data = candidate(); data.loc[0, "FinalScore"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "non-finite FinalScore"):
                subject.calculate_portfolio_risk_inputs(data)

    def test_non_finite_market_data_fails_closed(self):
        data = market(); data.loc[2, "Close"] = float("inf")
        result = self.calculate(data=data)
        self.assertEqual(result.at[0, "RiskValidationStatus"], "FAILED")

    def test_missing_required_history_is_fail_closed(self):
        result = self.calculate(data=market(20))
        self.assertEqual(result.at[0, "RiskStatus"], "PENDING")
        self.assertEqual(result.at[0, "RiskValidationStatus"], "FAILED")
        self.assertIn("requires 60 observations", result.at[0, "RiskValidationReason"])

    def test_zero_eligible_candidates_has_stable_schema(self):
        result = subject.calculate_portfolio_risk_inputs(candidate([("AAA", False)]))
        self.assertTrue(result.empty)
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_risk_model_version_is_deterministic(self):
        self.assertEqual(subject.RISK_MODEL_VERSION, "portfolio-risk-v3.8.1-r1")
        self.assertEqual(self.calculate().RiskModelVersion.unique().tolist(), [subject.RISK_MODEL_VERSION])

    def test_candidate_input_is_not_modified(self):
        data = candidate(); before = data.copy(deep=True); self.calculate(candidates=data)
        pd.testing.assert_frame_equal(data, before)

    def test_architecture_boundary_excludes_score_signal_and_legacy_fields(self):
        result = self.calculate()
        for forbidden in ("FinalScore", "TradeSignal", "PortfolioEligible", "BacktestScore", "SharpeRatio", "MaxDrawdown"):
            self.assertNotIn(forbidden, result.columns)

    def test_missing_portfolio_snapshot_is_pending_not_pass(self):
        result = subject.calculate_portfolio_risk_inputs(
            candidate(), market_data={"AAA": market()}, portfolio_snapshot=None,
            calculation_timestamp="2026-06-30T22:00:00+00:00",
        )
        self.assertEqual(result.at[0, "RiskStatus"], "PENDING")
        self.assertEqual(result.at[0, "RiskValidationStatus"], "FAILED")
        self.assertEqual(result.at[0, "RiskValidationReason"], "PORTFOLIO_SNAPSHOT_MISSING")

    def test_future_portfolio_snapshot_is_rejected(self):
        portfolio = snapshot(); portfolio.loc[0, "PortfolioAsOfDate"] = "2026-07-01"
        with self.assertRaisesRegex(ValueError, "future portfolio state"):
            self.calculate(portfolio=portfolio)

    def test_run_writes_without_modifying_candidate_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "candidates.csv"; output = root / "risk.csv"
            candidate([("AAA", False)]).to_csv(source, index=False); before = source.read_bytes()
            result, saved = subject.run_portfolio_risk_calculator(source, output)
            self.assertEqual(source.read_bytes(), before); self.assertEqual(saved, output)
            self.assertEqual(tuple(pd.read_csv(output).columns), subject.OUTPUT_COLUMNS)


if __name__ == "__main__":
    unittest.main()
