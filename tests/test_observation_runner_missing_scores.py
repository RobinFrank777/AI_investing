import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import observation_runner as subject


class ObservationRunnerScoreAuthorityTests(unittest.TestCase):
    status = {
        "StartTime": "2026-09-25T07:29:16+08:00",
        "UpdatedAt": "2026-09-25T07:33:44+08:00",
        "CurrentRunId": "run-1",
        "AsOfDate": "2026-09-24",
        "OverallRunStatus": "PASS",
    }

    def write_fundamental(self, path, rows, columns=None, mtime=None):
        pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
        if mtime is None:
            mtime = datetime.fromisoformat("2026-09-25T07:31:00+08:00").timestamp()
        os.utime(path, (mtime, mtime))

    def fundamental(self, path, ticker="AAA"):
        with patch.object(subject, "FUNDAMENTAL_SCORE_OUTPUT_PATH", path), patch.object(subject, "load_current_run_status", return_value=self.status):
            return subject._optional_fundamental_value(ticker)

    def combined(self, path, ticker="AAA"):
        with patch.object(subject, "COMBINED_SCORE_PATH", path):
            return subject._optional_combined_value(ticker, run_id="run-1", as_of_date="2026-09-24", universe_version="U1", score_model_version="S1")

    def test_fundamental_numeric_and_normalized_ticker(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            self.write_fundamental(path, [{"Ticker": "okta ", "FundamentalScore": 71.5}])
            self.assertEqual(self.fundamental(path, "OKTA"), 71.5)

    def test_fundamental_ticker_absent_returns_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            self.write_fundamental(path, [{"Ticker": "BBB", "FundamentalScore": 71.5}])
            self.assertEqual(self.fundamental(path), "MISSING")

    def test_fundamental_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError, "missing"):
                self.fundamental(Path(td) / "fundamental_score.csv")

    def test_fundamental_empty_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "empty"):
                self.fundamental(path)

    def test_fundamental_header_only_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            self.write_fundamental(path, [], columns=["Ticker", "FundamentalScore"])
            with self.assertRaisesRegex(RuntimeError, "empty"):
                self.fundamental(path)

    def test_duplicate_normalized_fundamental_ticker_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            self.write_fundamental(path, [{"Ticker": "OKTA", "FundamentalScore": 70}, {"Ticker": "okta ", "FundamentalScore": 71}])
            with self.assertRaisesRegex(RuntimeError, "normalized row"):
                self.fundamental(path, "OKTA")

    def test_missing_fundamental_columns_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            self.write_fundamental(path, [{"Ticker": "AAA", "Score": 70}])
            with self.assertRaisesRegex(RuntimeError, "FundamentalScore"):
                self.fundamental(path)

    def test_nan_fundamental_returns_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            self.write_fundamental(path, [{"Ticker": "AAA", "FundamentalScore": float("nan")}])
            self.assertEqual(self.fundamental(path), "MISSING")

    def test_fundamental_mtime_before_start_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            stamp = datetime.fromisoformat("2026-09-25T07:29:15.999+08:00").timestamp()
            self.write_fundamental(path, [{"Ticker": "AAA", "FundamentalScore": 70}], mtime=stamp)
            with self.assertRaisesRegex(RuntimeError, "predates"):
                self.fundamental(path)

    def test_fundamental_mtime_at_upper_bound_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            stamp = datetime.fromisoformat("2026-09-25T07:33:45+08:00").timestamp()
            self.write_fundamental(path, [{"Ticker": "AAA", "FundamentalScore": 70}], mtime=stamp)
            with self.assertRaisesRegex(RuntimeError, "newer"):
                self.fundamental(path)

    def test_fundamental_mtime_within_window_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            stamp = datetime.fromisoformat("2026-09-25T07:30:00+08:00").timestamp()
            self.write_fundamental(path, [{"Ticker": "AAA", "FundamentalScore": 70}], mtime=stamp)
            self.assertEqual(self.fundamental(path), 70.0)

    def test_same_second_updated_at_fraction_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fundamental_score.csv"
            stamp = datetime.fromisoformat("2026-09-25T07:33:44.500+08:00").timestamp()
            self.write_fundamental(path, [{"Ticker": "AAA", "FundamentalScore": 70}], mtime=stamp)
            self.assertEqual(self.fundamental(path), 70.0)

    def test_combined_absent_ticker_returns_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combined_score.csv"
            pd.DataFrame([{"Ticker":"BBB","RunId":"run-1","AsOfDate":"2026-09-24","UniverseVersion":"U1","ScoreModelVersion":"S1","CombinedScore":75}]).to_csv(path,index=False)
            self.assertEqual(self.combined(path), "MISSING")

    def test_combined_identity_mismatch_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combined_score.csv"
            pd.DataFrame([{"Ticker":"AAA","RunId":"wrong","AsOfDate":"2026-09-24","UniverseVersion":"U1","ScoreModelVersion":"S1","CombinedScore":75}]).to_csv(path,index=False)
            with self.assertRaisesRegex(RuntimeError, "RunId mismatch"):
                self.combined(path)

    def write_candidate_inputs(self, root, combined_rows, signal="WATCH"):
        candidates, rank, combined = root/"production_candidates.csv", root/"stock_rank.csv", root/"combined_score.csv"
        pd.DataFrame([{"Ticker":"OKTA","RunId":"run-1","AsOfDate":"2026-09-24","CandidateRank":1,"FinalScore":65.0,"TradeSignal":signal,"ScoreModelVersion":"S1","UniverseVersion":"U1"}]).to_csv(candidates,index=False)
        pd.DataFrame([{"Ticker":"OKTA","MarketDataDate":"2026-09-24","Close":100.0,"FinalScore":65.0,"TradeSignal":signal,"Reason":f"{signal} / Rank 1","ScoreModelVersion":"S1","UniverseVersion":"U1"}]).to_csv(rank,index=False)
        pd.DataFrame(combined_rows, columns=["Ticker","RunId","AsOfDate","UniverseVersion","ScoreModelVersion","CombinedScore"]).to_csv(combined,index=False)
        return candidates, rank, combined

    def build_preview(self, root, combined_rows, signal="WATCH"):
        candidates, rank, combined = self.write_candidate_inputs(root, combined_rows, signal)
        fundamental = root / "fundamental_score.csv"
        self.write_fundamental(fundamental, [{"Ticker":"OKTA","FundamentalScore":74.0}])
        with patch.multiple(subject, CANDIDATES_PATH=candidates, STOCK_RANK_PATH=rank, COMBINED_SCORE_PATH=combined, FUNDAMENTAL_SCORE_OUTPUT_PATH=fundamental), patch.object(subject, "load_current_run_status", return_value=self.status), patch.object(subject, "require_run_date", return_value=date(2026,9,25)):
            return subject.build_candidate_tracking_previews()[0]

    def test_watch_uses_fundamental_when_combined_ticker_absent(self):
        with tempfile.TemporaryDirectory() as td:
            item = self.build_preview(Path(td), [])
            self.assertEqual(item["FundamentalScore"], 74.0)
            self.assertEqual(item["CombinedScore"], "MISSING")

    def test_ticker_in_both_files_uses_independent_values(self):
        with tempfile.TemporaryDirectory() as td:
            row={"Ticker":"OKTA","RunId":"run-1","AsOfDate":"2026-09-24","UniverseVersion":"U1","ScoreModelVersion":"S1","CombinedScore":81.5}
            item = self.build_preview(Path(td), [row])
            self.assertEqual(item["FundamentalScore"], 74.0)
            self.assertEqual(item["CombinedScore"], 81.5)

    def test_buy_model_portfolio_path_keeps_independent_scores(self):
        with tempfile.TemporaryDirectory() as td:
            row={"Ticker":"OKTA","RunId":"run-1","AsOfDate":"2026-09-24","UniverseVersion":"U1","ScoreModelVersion":"S1","CombinedScore":81.5}
            item = self.build_preview(Path(td), [row], signal="BUY")
            self.assertEqual((item["FundamentalScore"], item["CombinedScore"]), (74.0, 81.5))

    def test_no_tracked_candidates_skip_fundamental_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"production_candidates.csv"
            pd.DataFrame([{"Ticker":"OKTA","RunId":"run-1","AsOfDate":"2026-09-24","CandidateRank":1,"FinalScore":59.0,"TradeSignal":"IGNORE","ScoreModelVersion":"S1","UniverseVersion":"U1"}]).to_csv(path,index=False)
            with patch.object(subject,"CANDIDATES_PATH",path), patch.object(subject,"FUNDAMENTAL_SCORE_OUTPUT_PATH",Path(td)/"missing.csv"), patch.object(subject,"require_run_date",return_value=date(2026,9,25)):
                self.assertEqual(subject.build_candidate_tracking_previews(), [])


if __name__ == "__main__":
    unittest.main()
