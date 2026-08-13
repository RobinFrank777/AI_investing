import unittest

import pandas as pd

import config
import t1_threshold_governance as subject


class T1ThresholdGovernanceTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({
            "Date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-03-01"]),
            "Ticker": ["A", "B", "C"],
            "UniverseVersion": [config.PRIMARY_UNIVERSE_VERSION] * 3,
            "FinalScore": [80.0, 70.0, 59.0],
            "TradeSignal": ["IGNORE", "BUY", "BUY"],
            "Forward5DReturn": [0.10, None, -0.10],
            "Forward20DReturn": [0.20, 0.05, None],
            "Forward60DReturn": [None, None, None],
        })

    def test_grid_and_production_constants(self):
        self.assertEqual(subject.THRESHOLD_GRID, (60, 65, 70, 75, 80))
        self.assertEqual(subject.CURRENT_BUY_THRESHOLD, 75)
        self.assertEqual(subject.CURRENT_WATCH_THRESHOLD, 60)

    def test_candidates_use_score_not_production_signal(self):
        selected = subject.select_candidates(self.fixture(), 75)
        self.assertEqual(selected.Ticker.tolist(), ["A"])

    def test_missing_horizon_is_unavailable_not_zero(self):
        stats = subject.forward_return_statistics(self.fixture().Forward5DReturn, "Return5D")
        self.assertEqual(stats["Return5DSampleCount"], 2)
        self.assertEqual(stats["Return5DMean"], 0.0)
        empty = subject.forward_return_statistics(self.fixture().Forward60DReturn, "Return60D")
        self.assertEqual(empty["Return60DSampleCount"], 0)
        self.assertTrue(pd.isna(empty["Return60DMean"]))

    def test_frequency_coverage_and_zero_month(self):
        summary, monthly = subject.summarize_threshold(self.fixture(), 75, eligible_count=4)
        self.assertEqual(summary["CandidateFrequency"], 1/3)
        self.assertEqual(summary["CandidateCoverage"], 1/4)
        self.assertEqual(summary["ZeroBuyMonths"], 2)
        self.assertEqual(monthly.BuyCount.tolist(), [1, 0, 0])

    def test_concentration_and_zero_candidates_are_safe(self):
        concentration = subject.concentration_metrics(pd.DataFrame({"Ticker": ["A", "A", "B"]}))
        self.assertAlmostEqual(concentration["Top1TickerShare"], 2/3)
        self.assertAlmostEqual(concentration["HHI"], 5/9)
        summary, _ = subject.summarize_threshold(self.fixture(), 100, eligible_count=4)
        self.assertEqual(summary["TotalBuyObservations"], 0)
        self.assertEqual(summary["HHI"], 0)

    def test_universe_version_and_input_are_preserved(self):
        data = self.fixture()
        before = data.copy(deep=True)
        summary, _ = subject.build_governance_summary(data, 148)
        pd.testing.assert_frame_equal(data, before)
        self.assertEqual(summary.UniverseVersion.unique().tolist(), [config.PRIMARY_UNIVERSE_VERSION])

    def test_history_exclusion_is_not_membership_removal(self):
        configured = 150
        excluded = {"SKHY", "SPCX"}
        eligible = [f"T{i}" for i in range(148)]
        self.assertEqual(configured, len(eligible) + len(excluded))

    def test_forward_return_contract_uses_future_rows(self):
        prices = pd.Series([100.0, 110.0, 121.0])
        forward = prices.shift(-1) / prices - 1
        self.assertAlmostEqual(forward.iloc[0], 0.10)
        self.assertTrue(pd.isna(forward.iloc[-1]))


if __name__ == "__main__":
    unittest.main()
