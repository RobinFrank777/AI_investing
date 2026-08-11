import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIERS_PATH = PROJECT_ROOT / "data" / "company_profile_tiers.csv"
UNIVERSE_PATH = PROJECT_ROOT / "data" / "AI_investing_universe_150_V2.csv"
EXPECTED_COLUMNS = ("ticker", "tier", "priority", "reason")
ALLOWED_TIERS = {"Tier1", "Tier2", "Tier3"}
ALLOWED_PRIORITIES = {"A", "B", "C"}


class CompanyProfileTiersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiers = pd.read_csv(TIERS_PATH)
        cls.universe = pd.read_csv(UNIVERSE_PATH)

    def test_csv_exists(self):
        self.assertTrue(TIERS_PATH.is_file())

    def test_required_columns_exist_in_order(self):
        self.assertEqual(tuple(self.tiers.columns), EXPECTED_COLUMNS)

    def test_tickers_are_unique(self):
        tickers = self.tiers["ticker"].astype(str).str.strip().str.upper()
        self.assertFalse(tickers.duplicated().any())

    def test_tier_and_priority_values_are_valid(self):
        self.assertTrue(self.tiers["tier"].isin(ALLOWED_TIERS).all())
        self.assertTrue(self.tiers["priority"].isin(ALLOWED_PRIORITIES).all())

    def test_all_tickers_exist_in_universe150(self):
        tier_tickers = set(
            self.tiers["ticker"].astype(str).str.strip().str.upper()
        )
        universe_tickers = set(
            self.universe["ticker"].astype(str).str.strip().str.upper()
        )
        self.assertEqual(tier_tickers - universe_tickers, set())


if __name__ == "__main__":
    unittest.main()
