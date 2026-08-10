import tempfile
import unittest
from pathlib import Path

import pandas as pd

import company_profile_validator as subject


def valid_data():
    return pd.DataFrame(
        [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "sector": "Technology",
                "industry": "Software",
                "country": "USA",
                "business_model": "Enterprise software and cloud platform",
                "investment_thesis": "Cloud and AI ecosystem growth",
                "moat_score": 5,
                "valuation_type": "Growth",
                "growth_driver": "Azure and AI adoption",
                "risk_factor": "Competition and regulation",
                "investment_stage": "MATURE",
                "investor_rating": 90,
                "last_update": "2026-08-10",
            }
        ],
        columns=subject.EXPECTED_COLUMNS,
    )


class CompanyProfileValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "company_profile.csv"

    def validate(self, data):
        data.to_csv(self.path, index=False)
        return subject.validate_company_profile(self.path)

    def assert_fails(self, data, error):
        result = self.validate(data)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(error in item for item in result["errors"]))

    def test_current_seed_data_passes(self):
        result = subject.validate_company_profile()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["companies"], 3)

    def test_missing_field_fails(self):
        self.assert_fails(valid_data().drop(columns=["company"]), "missing columns")

    def test_extra_field_fails(self):
        data = valid_data().assign(unexpected="value")
        self.assert_fails(data, "extra columns")

    def test_field_order_fails(self):
        columns = list(subject.EXPECTED_COLUMNS)
        columns[0], columns[1] = columns[1], columns[0]
        self.assert_fails(valid_data()[columns], "column order invalid")

    def test_duplicate_ticker_fails(self):
        data = pd.concat([valid_data(), valid_data()], ignore_index=True)
        self.assert_fails(data, "duplicate ticker: MSFT")

    def test_missing_value_fails(self):
        data = valid_data()
        data.loc[0, "company"] = None
        self.assert_fails(data, "missing values")

    def test_negative_moat_score_fails(self):
        data = valid_data()
        data.loc[0, "moat_score"] = -1
        self.assert_fails(data, "moat_score invalid")

    def test_moat_score_above_range_fails(self):
        data = valid_data()
        data.loc[0, "moat_score"] = 6
        self.assert_fails(data, "moat_score invalid")

    def test_fractional_moat_score_fails(self):
        data = valid_data()
        data["moat_score"] = data["moat_score"].astype(float)
        data.loc[0, "moat_score"] = 4.5
        self.assert_fails(data, "moat_score invalid")

    def test_investor_rating_above_range_fails(self):
        data = valid_data()
        data.loc[0, "investor_rating"] = 120
        self.assert_fails(data, "investor_rating invalid")

    def test_fractional_investor_rating_fails(self):
        data = valid_data()
        data["investor_rating"] = data["investor_rating"].astype(float)
        data.loc[0, "investor_rating"] = 90.5
        self.assert_fails(data, "investor_rating invalid")

    def test_non_numeric_investor_rating_fails(self):
        data = valid_data()
        data["investor_rating"] = data["investor_rating"].astype(object)
        data.loc[0, "investor_rating"] = "A"
        self.assert_fails(data, "investor_rating invalid")

    def test_dividend_valuation_type_fails(self):
        data = valid_data()
        data.loc[0, "valuation_type"] = "Dividend"
        self.assert_fails(data, "valuation_type invalid")

    def test_cyclical_valuation_type_passes(self):
        data = valid_data()
        data.loc[0, "valuation_type"] = "Cyclical"
        self.assertEqual(self.validate(data)["status"], "PASS")

    def test_asset_based_valuation_type_passes(self):
        data = valid_data()
        data.loc[0, "valuation_type"] = "Asset-Based"
        self.assertEqual(self.validate(data)["status"], "PASS")

    def test_unknown_investment_stage_fails(self):
        data = valid_data()
        data.loc[0, "investment_stage"] = "UNKNOWN"
        self.assert_fails(data, "investment_stage invalid")

    def test_cyclical_investment_stage_passes(self):
        data = valid_data()
        data.loc[0, "investment_stage"] = "CYCLICAL"
        self.assertEqual(self.validate(data)["status"], "PASS")

    def test_non_iso_last_update_fails(self):
        data = valid_data()
        data.loc[0, "last_update"] = "2026/08/10"
        self.assert_fails(data, "last_update invalid")

    def test_missing_file_fails(self):
        result = subject.validate_company_profile(self.path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("file not found" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
