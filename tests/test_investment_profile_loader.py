import tempfile
import unittest
from pathlib import Path

import pandas as pd

import investment_profile_loader as subject


class InvestmentProfileLoaderTests(unittest.TestCase):
    def test_load_existing_csv_successfully(self):
        profiles = subject.load_company_profiles()
        self.assertGreater(len(profiles), 0)
        self.assertEqual(tuple(profiles.columns), subject.EXPECTED_COLUMNS)

    def test_load_returns_dataframe(self):
        self.assertIsInstance(subject.load_company_profiles(), pd.DataFrame)

    def test_load_existing_ticker(self):
        profile = subject.load_company_profile("NVDA")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["ticker"], "NVDA")

    def test_unknown_ticker_returns_none(self):
        self.assertIsNone(subject.load_company_profile("UNKNOWN"))

    def test_missing_file_error_is_clear(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.csv"
            with self.assertRaisesRegex(
                FileNotFoundError, "Company Profile file not found"
            ):
                subject.load_company_profiles(missing)

    def test_returned_dictionary_contains_required_fields(self):
        profile = subject.load_company_profile("NVDA")
        self.assertEqual(tuple(profile), subject.EXPECTED_COLUMNS)


if __name__ == "__main__":
    unittest.main()
