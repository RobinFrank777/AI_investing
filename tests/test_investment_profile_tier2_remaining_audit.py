import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import investment_profile_coverage as coverage
import investment_profile_tier2_remaining_audit as subject


class InvestmentProfileTier2RemainingAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.universe_path = root / "universe.csv"
        self.tier_path = root / "tiers.csv"

        pd.DataFrame(
            [
                (1, "CSCO", "Cisco Systems", "Technology", "Cloud & platform", "AI platform / cloud infrastructure"),
                (2, "ZETA", "Zeta Global", "Technology", "Software", "Enterprise software / AI applications"),
                (3, "OKTA", "Okta", "Technology", "Software", "Enterprise software / AI applications"),
                (4, "QUBT", "Quantum Computing Inc.", "Technology", "Quantum computing", "Quantum computing"),
                (5, "PACS", "PACS Group", "Healthcare", "Healthcare services", "Healthcare services / digital health"),
            ],
            columns=["order", "ticker", "company", "sector", "industry", "theme"],
        ).to_csv(self.universe_path, index=False)
        pd.DataFrame(
            [
                ("CSCO", "Tier2", "B", "Enterprise network infrastructure"),
                ("ZETA", "Tier2", "B", "Enterprise AI application software"),
                ("OKTA", "Tier2", "B", "Identity and access platform"),
                ("QUBT", "Tier2", "B", "Quantum computing research candidate"),
                ("PACS", "Tier2", "B", "Healthcare services platform"),
            ],
            columns=coverage.TIER_COLUMNS,
        ).to_csv(self.tier_path, index=False)

    def run_audit(self):
        profiles = pd.DataFrame({"ticker": ["PACS"]})
        with mock.patch.object(coverage, "load_company_profiles", return_value=profiles):
            return subject.audit_remaining_tier2(
                self.universe_path, self.tier_path
            )

    def test_coverage_summary(self):
        result = self.run_audit()
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["existing_count"], 1)
        self.assertEqual(result["missing_count"], 4)
        self.assertEqual(result["coverage_rate"], 20.0)

    def test_existing_profiles_include_ticker_and_company(self):
        result = self.run_audit()
        self.assertEqual(
            result["existing"], [{"ticker": "PACS", "company": "PACS Group"}]
        )

    def test_missing_profiles_include_required_metadata(self):
        result = self.run_audit()
        first = result["missing"][0]
        self.assertEqual(first["ticker"], "CSCO")
        self.assertEqual(first["company"], "Cisco Systems")
        self.assertEqual(first["sector"], "Technology")
        self.assertEqual(first["industry"], "Cloud & platform")
        self.assertEqual(first["reason"], "Enterprise network infrastructure")

    def test_priority_reclassification(self):
        result = self.run_audit()
        self.assertEqual(result["priorities"]["A"], ["CSCO", "ZETA"])
        self.assertEqual(result["priorities"]["B"], ["OKTA"])
        self.assertEqual(result["priorities"]["C"], ["QUBT"])

    def test_next_batch_uses_missing_priority_a_companies(self):
        result = self.run_audit()
        self.assertEqual(
            [row["ticker"] for row in result["recommended_next_batch"]],
            ["ZETA", "CSCO"],
        )
        for row in result["recommended_next_batch"]:
            self.assertTrue(row["reason"])
            self.assertIn(row["ticker"], result["priorities"]["A"])

    def test_audit_does_not_create_investment_scores(self):
        result = self.run_audit()
        for record in result["missing"]:
            self.assertNotIn("score", record)
            self.assertNotIn("investor_rating", record)


if __name__ == "__main__":
    unittest.main()
