import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import investment_profile_coverage as coverage
import investment_profile_tier2_audit as subject


class InvestmentProfileTier2AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.universe_path = root / "universe.csv"
        self.tier_path = root / "tiers.csv"

        pd.DataFrame(
            [
                (1, "AI1", "AI Company", "Technology", "Semiconductors", "AI compute / semiconductor supply chain"),
                (2, "OKTA", "Identity Company", "Technology", "Software", "Enterprise software / AI applications"),
                (3, "BIO1", "Biotech Company", "Healthcare", "Biotechnology", "Early-stage biotechnology"),
                (4, "PACS", "PACS Group", "Healthcare", "Healthcare services", "Healthcare services / digital health"),
            ],
            columns=["order", "ticker", "company", "sector", "industry", "theme"],
        ).to_csv(self.universe_path, index=False)
        pd.DataFrame(
            [
                ("AI1", "Tier2", "B", "AI infrastructure candidate"),
                ("OKTA", "Tier2", "B", "Identity platform"),
                ("BIO1", "Tier2", "B", "Biotechnology candidate"),
                ("PACS", "Tier2", "B", "Healthcare services platform"),
            ],
            columns=coverage.TIER_COLUMNS,
        ).to_csv(self.tier_path, index=False)

    def run_audit(self):
        profiles = pd.DataFrame({"ticker": ["PACS"]})
        with mock.patch.object(coverage, "load_company_profiles", return_value=profiles):
            return subject.audit_tier2_coverage(
                self.universe_path, self.tier_path
            )

    def test_tier2_summary(self):
        result = self.run_audit()
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["existing"], 1)
        self.assertEqual(result["missing_count"], 3)
        self.assertEqual(result["coverage_rate"], 25.0)

    def test_covered_tier2_lists_ticker_and_company(self):
        result = self.run_audit()
        self.assertEqual(
            result["covered"], [{"ticker": "PACS", "company": "PACS Group"}]
        )

    def test_missing_tier2_contains_required_metadata(self):
        result = self.run_audit()
        first = result["missing"][0]
        self.assertEqual(first["ticker"], "AI1")
        self.assertEqual(first["company"], "AI Company")
        self.assertEqual(first["sector"], "Technology")
        self.assertEqual(first["industry"], "Semiconductors")
        self.assertEqual(first["reason"], "AI infrastructure candidate")

    def test_priority_classification_is_strategic_only(self):
        result = self.run_audit()
        self.assertEqual(result["priorities"]["A"], ["AI1"])
        self.assertEqual(result["priorities"]["B"], ["OKTA"])
        self.assertEqual(result["priorities"]["C"], ["BIO1"])

    def test_missing_records_do_not_contain_investment_scores(self):
        result = self.run_audit()
        for record in result["missing"]:
            self.assertNotIn("score", record)
            self.assertNotIn("investor_rating", record)


if __name__ == "__main__":
    unittest.main()
