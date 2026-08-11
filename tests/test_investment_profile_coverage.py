import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import investment_profile_coverage as subject


class InvestmentProfileCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.universe_path = Path(self.temp.name) / "universe.csv"
        self.tier_path = Path(self.temp.name) / "tiers.csv"

    def write_universe(self, tickers):
        pd.DataFrame({"ticker": tickers}).to_csv(self.universe_path, index=False)

    def write_tiers(self, rows):
        pd.DataFrame(rows, columns=subject.TIER_COLUMNS).to_csv(
            self.tier_path, index=False
        )

    def check_with_profiles(self, profile_tickers, tier_rows=None):
        if tier_rows is None:
            universe = pd.read_csv(self.universe_path)
            unique_tickers = list(
                dict.fromkeys(
                    universe["ticker"].astype(str).str.strip().str.upper()
                )
            )
            tier_rows = [
                (ticker, "Tier1", "A", "Test coverage")
                for ticker in unique_tickers
            ]
        self.write_tiers(tier_rows)
        profiles = pd.DataFrame({"ticker": profile_tickers})
        with mock.patch.object(subject, "load_company_profiles", return_value=profiles):
            return subject.check_profile_coverage(
                self.universe_path, self.tier_path
            )

    def test_full_coverage(self):
        self.write_universe(["MSFT", "NVDA", "RKLB"])
        result = self.check_with_profiles(["MSFT", "NVDA", "RKLB"])
        self.assertEqual(result["universe_count"], 3)
        self.assertEqual(result["profile_count"], 3)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["coverage_rate"], 100.0)
        self.assertEqual(result["missing_tickers"], [])

    def test_partial_coverage(self):
        self.write_universe(["MSFT", "NVDA", "RKLB"])
        result = self.check_with_profiles(["MSFT"])
        self.assertEqual(result["profile_count"], 1)
        self.assertEqual(result["missing_count"], 2)
        self.assertEqual(result["coverage_rate"], 33.33)
        self.assertEqual(result["missing_tickers"], ["NVDA", "RKLB"])

    def test_empty_profile_dataset(self):
        self.write_universe(["MSFT", "NVDA"])
        result = self.check_with_profiles([])
        self.assertEqual(result["profile_count"], 0)
        self.assertEqual(result["missing_count"], 2)
        self.assertEqual(result["coverage_rate"], 0.0)
        self.assertEqual(result["missing_tickers"], ["MSFT", "NVDA"])

    def test_duplicate_universe_tickers_are_counted_once(self):
        self.write_universe(["MSFT", " msft ", "NVDA", "NVDA"])
        result = self.check_with_profiles(["MSFT"])
        self.assertEqual(result["universe_count"], 2)
        self.assertEqual(result["profile_count"], 1)
        self.assertEqual(result["missing_tickers"], ["NVDA"])

    def test_invalid_universe_path(self):
        missing_path = Path(self.temp.name) / "missing.csv"
        with self.assertRaisesRegex(FileNotFoundError, "Stock universe file not found"):
            subject.check_profile_coverage(missing_path)

    def test_tier1_partial_coverage(self):
        self.write_universe(["MSFT", "NVDA", "RKLB"])
        rows = [
            ("MSFT", "Tier1", "A", "Core"),
            ("NVDA", "Tier1", "A", "Core"),
            ("RKLB", "Tier2", "B", "Research"),
        ]
        result = self.check_with_profiles(["MSFT", "RKLB"], rows)
        self.assertEqual(
            result["tiers"]["Tier1"],
            {
                "total": 2,
                "covered": 1,
                "missing": 1,
                "coverage_rate": 50.0,
                "missing_tickers": ["NVDA"],
            },
        )

    def test_tier2_partial_coverage(self):
        self.write_universe(["MSFT", "NVDA", "RKLB"])
        rows = [
            ("MSFT", "Tier1", "A", "Core"),
            ("NVDA", "Tier2", "B", "Research"),
            ("RKLB", "Tier2", "B", "Research"),
        ]
        result = self.check_with_profiles(["MSFT", "NVDA"], rows)
        self.assertEqual(result["tiers"]["Tier2"]["covered"], 1)
        self.assertEqual(result["tiers"]["Tier2"]["missing"], 1)
        self.assertEqual(result["tiers"]["Tier2"]["coverage_rate"], 50.0)
        self.assertEqual(result["tiers"]["Tier2"]["missing_tickers"], ["RKLB"])

    def test_full_tier_coverage(self):
        self.write_universe(["MSFT", "NVDA"])
        rows = [
            ("MSFT", "Tier1", "A", "Core"),
            ("NVDA", "Tier2", "B", "Research"),
        ]
        result = self.check_with_profiles(["MSFT", "NVDA"], rows)
        for metrics in result["tiers"].values():
            self.assertEqual(metrics["coverage_rate"], 100.0)
            self.assertEqual(metrics["missing_tickers"], [])

    def test_missing_tier_file(self):
        self.write_universe(["MSFT"])
        with self.assertRaisesRegex(FileNotFoundError, "tier file not found"):
            subject.check_profile_coverage(self.universe_path, self.tier_path)

    def test_empty_tier_file(self):
        self.write_universe(["MSFT"])
        self.tier_path.touch()
        with self.assertRaisesRegex(ValueError, "tier file is empty"):
            subject.check_profile_coverage(self.universe_path, self.tier_path)

    def test_invalid_tier_schema(self):
        self.write_universe(["MSFT"])
        pd.DataFrame({"ticker": ["MSFT"], "tier": ["Tier1"]}).to_csv(
            self.tier_path, index=False
        )
        with self.assertRaisesRegex(ValueError, "tier schema"):
            subject.check_profile_coverage(self.universe_path, self.tier_path)

    def test_duplicate_tier_tickers(self):
        self.write_universe(["MSFT"])
        self.write_tiers(
            [
                ("MSFT", "Tier1", "A", "Core"),
                (" msft ", "Tier2", "B", "Research"),
            ]
        )
        with self.assertRaisesRegex(ValueError, "Duplicate.*MSFT"):
            subject.check_profile_coverage(self.universe_path, self.tier_path)

    def test_unknown_tier_value(self):
        self.write_universe(["MSFT"])
        self.write_tiers([("MSFT", "Tier4", "A", "Unknown")])
        with self.assertRaisesRegex(ValueError, "Unknown.*Tier4"):
            subject.check_profile_coverage(self.universe_path, self.tier_path)

    def test_tier_ticker_outside_universe(self):
        self.write_universe(["MSFT"])
        self.write_tiers([("NVDA", "Tier1", "A", "Core")])
        with self.assertRaisesRegex(ValueError, "not in Universe150: NVDA"):
            subject.check_profile_coverage(self.universe_path, self.tier_path)


if __name__ == "__main__":
    unittest.main()
