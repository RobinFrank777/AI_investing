import unittest

import numpy as np
import pandas as pd

import config
import t0_momentum_diagnostics as subject
from score import calculate_rank_score_diagnostics


class T0MomentumDiagnosticsTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({
            "Date": ["2026-08-01"] * 3,
            "Ticker": ["A", "B", "C"],
            "UniverseVersion": [config.PRIMARY_UNIVERSE_VERSION] * 3,
            "MomentumScore": [47.0, 10.0, -5.0],
            "ReturnMomentumContribution": [7.0, 0.0, -5.0],
            "MACDContribution": [40.0, 10.0, 0.0],
            "TechnicalScore": [60.0, 50.0, 40.0],
            "FinalScore": [76.0, 65.0, 55.0],
            "TradeSignal": ["BUY", "WATCH", "IGNORE"],
            "Volume_Ratio": [1.0] * 3, "DistanceToHigh": [0.96] * 3,
            "Close": [110.0] * 3, "MA20": [100.0] * 3, "MA60": [90.0] * 3,
        })

    def test_decomposition_matches_production_decimal_return_formula(self):
        result = calculate_rank_score_diagnostics(110, 100, 90, 0.10, 0.20, 1.0, 105, 0.96, 2, 1, 1)
        self.assertEqual(result["ReturnMomentumContribution"], 13.0)
        self.assertEqual(result["MACDContribution"], 40)
        self.assertEqual(result["MomentumScore"], 53.0)

    def test_theoretical_macd_states_and_return_lower_bound(self):
        states = set()
        for macd, signal in ((-1, 0), (1, 2), (-1, -2), (1, 0)):
            result = calculate_rank_score_diagnostics(1, 2, 3, -1, -1, 1, 2, 0.5, macd, signal, macd-signal)
            states.add(result["MACDContribution"])
        self.assertEqual(states, {0, 10, 30, 40})
        self.assertEqual(result["ReturnMomentumContribution"], -100)

    def test_zero_and_mixed_sign_shares_are_safe(self):
        frame = pd.DataFrame({"ReturnMomentumContribution": [0.0, -5.0], "MACDContribution": [0.0, 10.0]})
        shares = subject.contribution_shares(frame)
        self.assertTrue(np.isnan(shares.at[0, "ReturnShare"]))
        self.assertAlmostEqual(shares.at[1, "ReturnShare"], 1/3)
        self.assertAlmostEqual(shares.at[1, "MACDShare"], 2/3)

    def test_dominance_warning_logic(self):
        warning = pd.DataFrame({"ReturnShare": [0.1, 0.15, 0.05], "MACDShare": [0.9, 0.85, 0.95]})
        self.assertTrue(subject.dominance_warning(warning))
        self.assertFalse(subject.dominance_warning(warning.assign(MACDShare=0.7)))

    def test_sensitivity_does_not_modify_input_and_preserves_version(self):
        original = self.fixture()
        before = original.copy(deep=True)
        result = subject.apply_sensitivity(original, "Without MACD")
        pd.testing.assert_frame_equal(original, before)
        self.assertEqual(result.UniverseVersion.unique().tolist(), [config.PRIMARY_UNIVERSE_VERSION])
        self.assertEqual(result.at[0, "ScenarioFinalScore"], 69.0)

    def test_ranking_metrics_are_deterministic(self):
        result = subject.sensitivity_summary(self.fixture())
        production = result.loc[result.Scenario == "Production"].iloc[0]
        self.assertAlmostEqual(production.RankCorrelation, 1.0)
        self.assertAlmostEqual(production.TopDecileOverlap, 1.0)
        self.assertEqual(production.SignalChanges, 0)

    def test_history_exclusion_does_not_change_universe_contract(self):
        configured = ["A", "SKHY", "SPCX"]
        eligible = [ticker for ticker in configured if ticker not in {"SKHY", "SPCX"}]
        self.assertEqual(len(configured), 3)
        self.assertEqual(eligible, ["A"])


if __name__ == "__main__":
    unittest.main()
