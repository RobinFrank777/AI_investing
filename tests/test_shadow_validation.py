import tempfile
import unittest
from pathlib import Path

import pandas as pd

import shadow_validation as subject


def candidate(ticker="AAA", date="2026-06-30", run="run-1", eligible=True, rank=1):
    return {
        "Ticker": ticker, "RunId": run, "AsOfDate": date,
        "ScoreModelVersion": "technical-score-v3.8.1-r1",
        "CandidateRank": rank, "FinalScore": 80.0, "TradeSignal": "BUY",
        "Eligibility": "ELIGIBLE", "PortfolioEligible": eligible,
        "ValidationStatus": "PASS", "ValidationReason": "",
    }


def risk(ticker="AAA", date="2026-06-30", run="run-1", status="READY", validation="PASS"):
    return {
        "Ticker": ticker, "RunId": run, "AsOfDate": date,
        "ScoreModelVersion": "technical-score-v3.8.1-r1",
        "RiskModelVersion": "portfolio-risk-v3.8.1-r1",
        "RiskStatus": status, "RiskValidationStatus": validation,
        "RiskValidationReason": "" if validation == "PASS" else "fixture failure",
        "ObservationEndDate": date,
    }


class ShadowValidationTests(unittest.TestCase):
    def validate(self, candidates=None, risks=None):
        candidates = pd.DataFrame([candidate()]) if candidates is None else candidates
        risks = pd.DataFrame([risk()]) if risks is None else risks
        return subject.validate_shadow(candidates, risks)

    def test_exact_key_ready(self):
        report, metrics = self.validate()
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_READY")
        self.assertEqual(metrics["MatchedEligibleRows"], 1)
        self.assertEqual(metrics["ShadowReadyCoveragePercent"], 100.0)

    def test_same_ticker_different_date_does_not_match(self):
        report, _ = self.validate(risks=pd.DataFrame([risk(date="2026-06-29")]))
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_METADATA_MISMATCH")
        self.assertEqual(report.at[0, "ShadowReason"], "AS_OF_DATE_MISMATCH")

    def test_same_ticker_date_different_run_does_not_match(self):
        report, _ = self.validate(risks=pd.DataFrame([risk(run="run-2")]))
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_METADATA_MISMATCH")
        self.assertEqual(report.at[0, "ShadowReason"], "RUN_ID_MISMATCH")

    def test_score_model_mismatch_is_not_ready(self):
        risks = pd.DataFrame([risk()]); risks.loc[0, "ScoreModelVersion"] = "other-model"
        report, _ = self.validate(risks=risks)
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_METADATA_MISMATCH")
        self.assertEqual(report.at[0, "ShadowReason"], "SCORE_MODEL_VERSION_MISMATCH")

    def test_pending_is_not_ready(self):
        report, _ = self.validate(risks=pd.DataFrame([risk(status="PENDING", validation="FAILED")]))
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_PENDING")

    def test_blocked_is_not_ready(self):
        report, _ = self.validate(risks=pd.DataFrame([risk(status="BLOCKED", validation="FAILED")]))
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_BLOCKED")

    def test_missing_risk_is_explicit(self):
        empty_risk = pd.DataFrame(columns=subject.RISK_COLUMNS)
        report, metrics = self.validate(risks=empty_risk)
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_MISSING_RISK")
        self.assertEqual(metrics["MissingRiskRows"], 1)

    def test_zero_eligible_has_stable_schema_and_no_ready(self):
        report, metrics = self.validate(
            candidates=pd.DataFrame([candidate(eligible=False)]),
            risks=pd.DataFrame(columns=subject.RISK_COLUMNS),
        )
        self.assertTrue(report.empty)
        self.assertEqual(tuple(report.columns), subject.OUTPUT_COLUMNS)
        self.assertEqual(metrics["PortfolioEligibleRows"], 0)
        self.assertIsNone(metrics["ShadowReadyCoveragePercent"])
        self.assertEqual(
            metrics["FailureReasons"], {"NO_PORTFOLIO_ELIGIBLE_CANDIDATE": 1}
        )

    def test_duplicate_candidate_key_fails_closed(self):
        candidates = pd.DataFrame([candidate(), candidate()])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANDIDATE"):
            self.validate(candidates=candidates)

    def test_duplicate_risk_key_fails_closed(self):
        risks = pd.DataFrame([risk(), risk()])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RISK_ROW"):
            self.validate(risks=risks)

    def test_inputs_are_not_modified(self):
        candidates = pd.DataFrame([candidate(ticker=" aaa ")]); risks = pd.DataFrame([risk(ticker=" aaa ")])
        candidate_before = candidates.copy(deep=True); risk_before = risks.copy(deep=True)
        self.validate(candidates=candidates, risks=risks)
        pd.testing.assert_frame_equal(candidates, candidate_before)
        pd.testing.assert_frame_equal(risks, risk_before)

    def test_ordering_is_deterministic(self):
        candidates = pd.DataFrame([
            candidate("CCC", "2026-07-02", "run-3", rank=2),
            candidate("AAA", "2026-06-30", "run-1", rank=1),
            candidate("BBB", "2026-07-01", "run-2", rank=1),
        ])
        risks = pd.DataFrame([
            risk("BBB", "2026-07-01", "run-2"),
            risk("CCC", "2026-07-02", "run-3"),
            risk("AAA", "2026-06-30", "run-1"),
        ])
        report, metrics = self.validate(candidates, risks)
        self.assertEqual(report.Ticker.tolist(), ["AAA", "BBB", "CCC"])
        self.assertEqual(report.ShadowStatus.tolist(), ["SHADOW_READY"] * 3)
        self.assertEqual(metrics["MatchedEligibleRows"], 3)

    def test_future_observation_date_is_blocked(self):
        risks = pd.DataFrame([risk()]); risks.loc[0, "ObservationEndDate"] = "2026-07-01"
        report, _ = self.validate(risks=risks)
        self.assertEqual(report.at[0, "ShadowStatus"], "SHADOW_BLOCKED")
        self.assertEqual(report.at[0, "ShadowReason"], "FUTURE_OBSERVATION_DATE")

    def test_orphan_risk_row_is_counted_and_reported(self):
        risks = pd.DataFrame([risk(), risk(ticker="ORPHAN")])
        _, metrics = self.validate(risks=risks)
        self.assertEqual(metrics["OrphanRiskRows"], 1)
        self.assertEqual(metrics["FailureReasons"]["RISK_ROW_ORPHAN"], 1)

    def test_no_production_action_or_legacy_fields(self):
        report, _ = self.validate()
        for forbidden in subject.FORBIDDEN_OUTPUT_COLUMNS:
            self.assertNotIn(forbidden, report.columns)

    def test_run_does_not_modify_input_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate_path = root / "candidates.csv"
            risk_path = root / "risk.csv"
            output_path = root / "shadow.csv"
            pd.DataFrame([candidate()]).to_csv(candidate_path, index=False)
            pd.DataFrame([risk()]).to_csv(risk_path, index=False)
            candidate_before = candidate_path.read_bytes()
            risk_before = risk_path.read_bytes()
            report, metrics, saved = subject.run_shadow_validation(
                candidate_path, risk_path, output_path
            )
            self.assertEqual(candidate_path.read_bytes(), candidate_before)
            self.assertEqual(risk_path.read_bytes(), risk_before)
            self.assertEqual(saved, output_path)
            self.assertEqual(tuple(pd.read_csv(output_path).columns), subject.OUTPUT_COLUMNS)
            self.assertEqual(metrics["ShadowReadyRows"], 1)


if __name__ == "__main__":
    unittest.main()
