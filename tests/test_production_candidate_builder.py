import tempfile
import unittest
from pathlib import Path

import pandas as pd

import production_candidate_builder as subject
from config import PRIMARY_UNIVERSE_VERSION


def stock_rank():
    return pd.DataFrame(
        {
            "Ticker": ["BBB", "AAA", "CCC"],
            "MarketDataDate": ["2026-08-11"] * 3,
            "FinalScore": [75.0, 75.0, 60.0],
            "TradeSignal": ["BUY", "WATCH", "IGNORE"],
            "RS_Score": [90.0, 80.0, 70.0],
            "NearHighScore": [30.0, 20.0, 10.0],
            "Confidence": [85.0, 75.0, 65.0],
            "ScoreModelVersion": ["technical-score-v3.8.1-r1"] * 3,
            "UniverseVersion": [PRIMARY_UNIVERSE_VERSION] * 3,
        }
    )


class ProductionCandidateBuilderTests(unittest.TestCase):
    def test_preserves_fields_and_adds_contract_metadata(self):
        result = subject.build_production_candidates(
            stock_rank(), reference_date="2026-08-12"
        )
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(result["Ticker"].tolist(), ["AAA", "BBB", "CCC"])
        self.assertEqual(result["CandidateRank"].tolist(), [1, 2, 3])
        self.assertEqual(result["AsOfDate"].unique().tolist(), ["2026-08-11"])
        self.assertEqual(result["Eligibility"].tolist(), ["INELIGIBLE", "ELIGIBLE", "INELIGIBLE"])
        for field in (
            "FinalScore", "TradeSignal", "RS_Score", "NearHighScore",
            "Confidence", "ScoreModelVersion",
            "UniverseVersion",
        ):
            expected = stock_rank().set_index("Ticker").loc[result["Ticker"], field].tolist()
            self.assertEqual(result[field].tolist(), expected)

    def test_ranking_and_run_id_are_deterministic(self):
        first = subject.build_production_candidates(
            stock_rank(), reference_date="2026-08-12"
        )
        second = subject.build_production_candidates(
            stock_rank().sample(frac=1, random_state=5), reference_date="2026-08-12"
        )
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(len(first["RunId"].unique()), 1)
        self.assertRegex(first.at[0, "RunId"], r"^candidate-20260811-[0-9a-f]{12}$")

    def test_duplicate_ticker_is_rejected_after_normalization(self):
        data = stock_rank()
        data.loc[1, "Ticker"] = " bbb "
        with self.assertRaisesRegex(ValueError, "duplicate ticker: BBB"):
            subject.build_production_candidates(data, reference_date="2026-08-12")

    def test_missing_metadata_is_rejected(self):
        for column in subject.SOURCE_COLUMNS:
            with self.subTest(column=column):
                with self.assertRaisesRegex(ValueError, column):
                    subject.build_production_candidates(
                        stock_rank().drop(columns=[column]),
                        reference_date="2026-08-12",
                    )

    def test_mixed_date_and_model_version_are_rejected(self):
        mixed_date = stock_rank()
        mixed_date.loc[1, "MarketDataDate"] = "2026-08-10"
        with self.assertRaisesRegex(ValueError, "mixed MarketDataDate"):
            subject.build_production_candidates(mixed_date, reference_date="2026-08-12")
        mixed_version = stock_rank()
        mixed_version.loc[1, "ScoreModelVersion"] = "other"
        with self.assertRaisesRegex(ValueError, "mixed ScoreModelVersion"):
            subject.build_production_candidates(mixed_version, reference_date="2026-08-12")

    def test_missing_or_mismatched_universe_version_is_rejected(self):
        missing = stock_rank().drop(columns=["UniverseVersion"])
        with self.assertRaisesRegex(ValueError, "UniverseVersion"):
            subject.build_production_candidates(missing, reference_date="2026-08-12")
        mismatch = stock_rank()
        mismatch["UniverseVersion"] = "legacy-19"
        with self.assertRaisesRegex(ValueError, "MISMATCH"):
            subject.build_production_candidates(mismatch, reference_date="2026-08-12")

    def test_stale_and_future_data_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "is stale"):
            subject.build_production_candidates(
                stock_rank(), reference_date="2026-08-20"
            )
        with self.assertRaisesRegex(ValueError, "in the future"):
            subject.build_production_candidates(
                stock_rank(), reference_date="2026-08-10"
            )

    def test_non_finite_scores_are_rejected(self):
        for column, value in (("FinalScore", float("nan")), ("RS_Score", float("inf")), ("Confidence", float("-inf"))):
            with self.subTest(column=column):
                data = stock_rank()
                data.loc[0, column] = value
                with self.assertRaisesRegex(ValueError, f"non-finite {column}"):
                    subject.build_production_candidates(data, reference_date="2026-08-12")

    def test_empty_input_returns_stable_schema(self):
        empty = stock_rank().iloc[0:0]
        result = subject.build_production_candidates(empty, reference_date="2026-08-12")
        self.assertTrue(result.empty)
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)

    def test_run_writes_output_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "stock_rank.csv"
            output = root / "production_candidates.csv"
            stock_rank().to_csv(source, index=False)
            result, path = subject.run_production_candidate_builder(
                source, output, reference_date="2026-08-12"
            )
            self.assertEqual(path, output)
            pd.testing.assert_frame_equal(pd.read_csv(output), result)

    def test_source_data_is_not_modified(self):
        data = stock_rank()
        before = data.copy(deep=True)
        subject.build_production_candidates(data, reference_date="2026-08-12")
        pd.testing.assert_frame_equal(data, before)


if __name__ == "__main__":
    unittest.main()
