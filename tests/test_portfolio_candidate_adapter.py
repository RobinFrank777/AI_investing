import tempfile
import unittest
from pathlib import Path

import pandas as pd

import portfolio_candidate_adapter as subject
from config import PRIMARY_UNIVERSE_VERSION


def candidates():
    return pd.DataFrame(
        {
            "Ticker": ["AAA", "BBB", "CCC"],
            "AsOfDate": ["2026-08-11"] * 3,
            "RunId": ["candidate-run-1"] * 3,
            "UniverseVersion": [PRIMARY_UNIVERSE_VERSION] * 3,
            "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * 3,
            "CandidateRank": [1, 2, 3],
            "FinalScore": [80.0, 70.0, 40.0],
            "TradeSignal": ["BUY", "WATCH", "IGNORE"],
            "Eligibility": ["ELIGIBLE", "INELIGIBLE", "INELIGIBLE"],
        }
    )


class PortfolioCandidateAdapterTests(unittest.TestCase):
    def test_valid_buy_candidate_is_accepted_with_pending_risk(self):
        result = subject.build_validated_portfolio_candidates(candidates())
        self.assertTrue(bool(result.loc[0, "PortfolioEligible"]))
        self.assertEqual(result.loc[0, "ValidationStatus"], "RISK_INPUT_PENDING")
        self.assertIn("risk inputs are pending", result.loc[0, "ValidationReason"])

    def test_watch_is_not_portfolio_eligible(self):
        result = subject.build_validated_portfolio_candidates(candidates())
        self.assertFalse(bool(result.loc[1, "PortfolioEligible"]))
        self.assertEqual(result.loc[1, "ValidationStatus"], "NOT_PORTFOLIO_ELIGIBLE")
        self.assertIn("WATCH", result.loc[1, "ValidationReason"])

    def test_ignore_is_not_portfolio_eligible(self):
        result = subject.build_validated_portfolio_candidates(candidates())
        self.assertFalse(bool(result.loc[2, "PortfolioEligible"]))
        self.assertIn("IGNORE", result.loc[2, "ValidationReason"])

    def test_empty_candidate_set_is_safe(self):
        result = subject.build_validated_portfolio_candidates(candidates().iloc[0:0])
        self.assertTrue(result.empty)
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_duplicate_ticker_is_rejected(self):
        data = candidates()
        data.loc[1, "Ticker"] = " aaa "
        with self.assertRaisesRegex(ValueError, "duplicate ticker: AAA"):
            subject.build_validated_portfolio_candidates(data)

    def test_mixed_run_id_is_rejected(self):
        data = candidates()
        data.loc[1, "RunId"] = "candidate-run-2"
        with self.assertRaisesRegex(ValueError, "mixed RunId"):
            subject.build_validated_portfolio_candidates(data)

    def test_mixed_as_of_date_is_rejected(self):
        data = candidates()
        data.loc[1, "AsOfDate"] = "2026-08-10"
        with self.assertRaisesRegex(ValueError, "mixed AsOfDate"):
            subject.build_validated_portfolio_candidates(data)

    def test_missing_final_score_column_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FinalScore"):
            subject.build_validated_portfolio_candidates(
                candidates().drop(columns=["FinalScore"])
            )

    def test_nan_final_score_is_rejected(self):
        data = candidates()
        data.loc[0, "FinalScore"] = float("nan")
        with self.assertRaisesRegex(ValueError, "non-finite FinalScore"):
            subject.build_validated_portfolio_candidates(data)

    def test_infinite_final_score_is_rejected(self):
        data = candidates()
        data.loc[0, "FinalScore"] = float("inf")
        with self.assertRaisesRegex(ValueError, "non-finite FinalScore"):
            subject.build_validated_portfolio_candidates(data)

    def test_output_has_stable_schema(self):
        result = subject.build_validated_portfolio_candidates(candidates())
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_input_csv_is_not_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "production_candidates.csv"
            output_path = root / "validated_portfolio_candidates.csv"
            candidates().to_csv(source_path, index=False)
            before = source_path.read_bytes()

            result, saved = subject.run_portfolio_candidate_adapter(
                source_path, output_path
            )

            self.assertEqual(source_path.read_bytes(), before)
            self.assertEqual(saved, output_path)
            pd.testing.assert_frame_equal(pd.read_csv(output_path), result)

    def test_mixed_score_model_version_is_rejected(self):
        data = candidates()
        data.loc[1, "ScoreModelVersion"] = "other"
        with self.assertRaisesRegex(ValueError, "mixed ScoreModelVersion"):
            subject.build_validated_portfolio_candidates(data)

    def test_universe_version_is_preserved(self):
        result = subject.build_validated_portfolio_candidates(candidates())
        self.assertEqual(result.UniverseVersion.unique().tolist(), [PRIMARY_UNIVERSE_VERSION])

    def test_missing_universe_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UniverseVersion"):
            subject.build_validated_portfolio_candidates(candidates().drop(columns=["UniverseVersion"]))

    def test_mismatched_universe_version_is_rejected(self):
        data = candidates(); data.loc[:, "UniverseVersion"] = "legacy-universe"
        with self.assertRaisesRegex(ValueError, "incompatible UniverseVersion"):
            subject.build_validated_portfolio_candidates(data)

    def test_mixed_universe_version_is_rejected(self):
        data = candidates(); data.loc[1, "UniverseVersion"] = "legacy-universe"
        with self.assertRaisesRegex(ValueError, "mixed UniverseVersion"):
            subject.build_validated_portfolio_candidates(data)

    def test_buy_with_ineligible_source_state_is_not_accepted(self):
        data = candidates().iloc[[0]].copy()
        data.loc[:, "Eligibility"] = "INELIGIBLE"
        result = subject.build_validated_portfolio_candidates(data)
        self.assertFalse(bool(result.loc[0, "PortfolioEligible"]))


if __name__ == "__main__":
    unittest.main()
