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

    def write_universe(self, tickers):
        pd.DataFrame({"ticker": tickers}).to_csv(self.universe_path, index=False)

    def check_with_profiles(self, profile_tickers):
        profiles = pd.DataFrame({"ticker": profile_tickers})
        with mock.patch.object(subject, "load_company_profiles", return_value=profiles):
            return subject.check_profile_coverage(self.universe_path)

    def test_full_coverage(self):
        self.write_universe(["MSFT", "NVDA", "RKLB"])
        result = self.check_with_profiles(["MSFT", "NVDA", "RKLB"])
        self.assertEqual(
            result,
            {
                "universe_count": 3,
                "profile_count": 3,
                "missing_count": 0,
                "coverage_rate": 100.0,
                "missing_tickers": [],
            },
        )

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


if __name__ == "__main__":
    unittest.main()
