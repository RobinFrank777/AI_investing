
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import observation_runner as subject


class ObservationRunnerMissingScoresTests(unittest.TestCase):
    def call_optional(self):
        return subject._optional_combined_values(
            "AAA",
            run_id="run-1",
            as_of_date="2026-09-14",
            universe_version="U1",
            score_model_version="S1",
        )

    def test_missing_file_returns_explicit_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "combined_score.csv"
            with patch.object(subject, "COMBINED_SCORE_PATH", missing):
                self.assertEqual(self.call_optional(), ("MISSING", "MISSING"))

    def test_empty_file_returns_explicit_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combined_score.csv"
            pd.DataFrame(
                columns=[
                    "Ticker", "RunId", "AsOfDate", "UniverseVersion",
                    "ScoreModelVersion", "FundamentalScore", "CombinedScore",
                ]
            ).to_csv(path, index=False)
            with patch.object(subject, "COMBINED_SCORE_PATH", path):
                self.assertEqual(self.call_optional(), ("MISSING", "MISSING"))

    def test_no_matching_ticker_returns_explicit_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combined_score.csv"
            pd.DataFrame([{
                "Ticker": "BBB",
                "RunId": "run-1",
                "AsOfDate": "2026-09-14",
                "UniverseVersion": "U1",
                "ScoreModelVersion": "S1",
                "FundamentalScore": 70.0,
                "CombinedScore": 75.0,
            }]).to_csv(path, index=False)
            with patch.object(subject, "COMBINED_SCORE_PATH", path):
                self.assertEqual(self.call_optional(), ("MISSING", "MISSING"))

    def test_nan_scores_return_explicit_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combined_score.csv"
            pd.DataFrame([{
                "Ticker": "AAA",
                "RunId": "run-1",
                "AsOfDate": "2026-09-14",
                "UniverseVersion": "U1",
                "ScoreModelVersion": "S1",
                "FundamentalScore": float("nan"),
                "CombinedScore": float("nan"),
            }]).to_csv(path, index=False)
            with patch.object(subject, "COMBINED_SCORE_PATH", path):
                self.assertEqual(self.call_optional(), ("MISSING", "MISSING"))

    def test_numeric_scores_remain_numeric(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combined_score.csv"
            pd.DataFrame([{
                "Ticker": "AAA",
                "RunId": "run-1",
                "AsOfDate": "2026-09-14",
                "UniverseVersion": "U1",
                "ScoreModelVersion": "S1",
                "FundamentalScore": 70.5,
                "CombinedScore": 76.25,
            }]).to_csv(path, index=False)
            with patch.object(subject, "COMBINED_SCORE_PATH", path):
                self.assertEqual(self.call_optional(), (70.5, 76.25))


if __name__ == "__main__":
    unittest.main()
