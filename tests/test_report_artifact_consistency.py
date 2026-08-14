import tempfile
import unittest
from pathlib import Path

import pandas as pd

import backtest_engine
import config
import report_artifact_consistency as subject
import report_terminal


RUN_ID = "candidate-20260813-test"
AS_OF_DATE = "2026-08-13"
SCORE_VERSION = "technical-score-v3.8.1-r1"
RISK_VERSION = "risk-model-v3.8.2-p2"


def metadata(*, risk=True):
    values = {
        "RunId": [RUN_ID],
        "AsOfDate": [AS_OF_DATE],
        "UniverseVersion": [config.PRIMARY_UNIVERSE_VERSION],
        "ScoreModelVersion": [SCORE_VERSION],
    }
    if risk:
        values["RiskModelVersion"] = [RISK_VERSION]
    return values


def artifacts(*, action=True):
    candidate = pd.DataFrame(
        {
            **metadata(risk=False),
            "Ticker": ["AAA"],
            "Eligibility": ["ELIGIBLE" if action else "INELIGIBLE"],
            "TradeSignal": ["BUY" if action else "WATCH"],
        }
    )
    result = {"Production Candidate": candidate}
    for name in subject.ACTION_ARTIFACTS:
        frame = pd.DataFrame({**metadata(), "Ticker": ["AAA"]})
        if name == "Portfolio Risk":
            frame["PortfolioEligible"] = True
            frame["RiskStatus"] = "RISK_READY"
            frame["RiskReadyForPortfolio"] = True
        if name == "Model Portfolio":
            frame["PortfolioStatus"] = "PORTFOLIO_READY"
        if name == "Position Sizing":
            frame["TargetShares"] = 1
        if name == "Order Draft":
            frame["OrderStatus"] = "DRAFT_ONLY"
        if name == "Order Review":
            frame["ReviewStatus"] = "PASS"
            frame["PortfolioReviewFlag"] = "PASS"
        result[name] = frame
    return result


class ReportArtifactConsistencyTests(unittest.TestCase):
    def evaluate(self, values):
        return subject.evaluate_report_artifacts(values, report_date=AS_OF_DATE)

    def test_all_required_metadata_consistent_is_pass(self):
        result = self.evaluate(artifacts())
        self.assertEqual(result.status, subject.PASS)
        self.assertEqual(result.metadata["RunId"], RUN_ID)

    def test_run_id_mismatch_is_incompatible(self):
        values = artifacts()
        values["Order Draft"].loc[:, "RunId"] = "other-run"
        self.assertEqual(self.evaluate(values).status, subject.INCOMPATIBLE)

    def test_as_of_date_mismatch_is_stale(self):
        values = artifacts()
        values["Order Draft"].loc[:, "AsOfDate"] = "2026-08-12"
        self.assertEqual(self.evaluate(values).status, subject.STALE)

    def test_universe_mismatch_is_incompatible(self):
        values = artifacts()
        values["Production Candidate"].loc[:, "UniverseVersion"] = "legacy"
        self.assertEqual(self.evaluate(values).status, subject.INCOMPATIBLE)

    def test_universe_missing_is_unknown(self):
        values = artifacts()
        values["Production Candidate"] = values["Production Candidate"].drop(
            columns=["UniverseVersion"]
        )
        self.assertEqual(self.evaluate(values).status, subject.UNKNOWN)

    def test_score_model_mismatch_is_incompatible(self):
        values = artifacts()
        values["Position Sizing"].loc[:, "ScoreModelVersion"] = "other-score"
        self.assertEqual(self.evaluate(values).status, subject.INCOMPATIBLE)

    def test_score_model_missing_is_unknown(self):
        values = artifacts()
        values["Order Draft"] = values["Order Draft"].drop(
            columns=["ScoreModelVersion"]
        )
        self.assertEqual(self.evaluate(values).status, subject.UNKNOWN)

    def test_risk_model_mismatch_is_incompatible(self):
        values = artifacts()
        values["Order Review"].loc[:, "RiskModelVersion"] = "other-risk"
        self.assertEqual(self.evaluate(values).status, subject.INCOMPATIBLE)

    def test_risk_model_missing_is_unknown(self):
        values = artifacts()
        values["Model Portfolio"] = values["Model Portfolio"].drop(
            columns=["RiskModelVersion"]
        )
        self.assertEqual(self.evaluate(values).status, subject.UNKNOWN)

    def test_missing_current_candidate_does_not_search_legacy(self):
        result = self.evaluate({"Production Candidate": None})
        self.assertEqual(result.status, subject.UNKNOWN)
        self.assertNotIn("backtest", " ".join(result.reasons).lower())

    def test_empty_candidate_is_no_action_not_failed(self):
        empty = pd.DataFrame(columns=artifacts()["Production Candidate"].columns)
        result = self.evaluate({"Production Candidate": empty})
        self.assertEqual(result.status, subject.NO_ACTION)
        self.assertNotEqual(result.status, subject.FAILED)

    def test_no_eligible_candidate_makes_action_artifacts_optional(self):
        values = {"Production Candidate": artifacts(action=False)["Production Candidate"]}
        self.assertEqual(self.evaluate(values).status, subject.NO_ACTION)

    def test_required_artifact_validation_failure_is_failed(self):
        values = artifacts()
        values["Portfolio Risk"].loc[:, "RiskStatus"] = "INSUFFICIENT_HISTORY"
        values["Portfolio Risk"].loc[:, "RiskReadyForPortfolio"] = False
        result = self.evaluate(values)
        self.assertEqual(result.status, subject.FAILED)
        self.assertIn("no RISK_READY evidence", " ".join(result.reasons))

    def test_partial_risk_ready_is_not_failed(self):
        values = artifacts()
        extra = values["Portfolio Risk"].copy()
        extra.loc[:, "Ticker"] = "BBB"
        extra.loc[:, "RiskStatus"] = "INSUFFICIENT_HISTORY"
        extra.loc[:, "RiskReadyForPortfolio"] = False
        values["Portfolio Risk"] = pd.concat(
            [values["Portfolio Risk"], extra], ignore_index=True
        )
        self.assertEqual(self.evaluate(values).status, subject.PASS)

    def test_required_artifact_schema_failure_is_failed(self):
        values = artifacts()
        values["Order Draft"] = values["Order Draft"].drop(columns=["OrderStatus"])
        self.assertEqual(self.evaluate(values).status, subject.FAILED)

    def test_mixed_run_id_inside_artifact_never_passes(self):
        values = artifacts()
        duplicate = pd.concat([values["Order Draft"]] * 2, ignore_index=True)
        duplicate.loc[1, "RunId"] = "other-run"
        values["Order Draft"] = duplicate
        self.assertEqual(self.evaluate(values).status, subject.INCOMPATIBLE)

    def test_stale_candidate_is_stale(self):
        values = artifacts(action=False)
        values["Production Candidate"].loc[:, "AsOfDate"] = "2026-08-01"
        self.assertEqual(self.evaluate(values).status, subject.STALE)

    def test_legacy_backtest_remains_research_only(self):
        self.assertEqual(backtest_engine.BACKTEST_AUTHORITY, subject.RESEARCH_ONLY)

    def test_loader_uses_only_explicit_current_paths(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            legacy = root / "backtest_qualified_20d.csv"
            legacy.write_text("Ticker\nAAA\n", encoding="utf-8")
            loaded = subject.load_current_report_artifacts(
                {"Production Candidate": root / "missing.csv"}
            )
        self.assertIsNone(loaded["Production Candidate"])

    def test_current_report_displays_evidence_metadata(self):
        assessment = self.evaluate(artifacts())
        html = report_terminal.build_html([], assessment)
        for expected in (
            "Report Status", RUN_ID, AS_OF_DATE,
            config.PRIMARY_UNIVERSE_VERSION, SCORE_VERSION, RISK_VERSION,
        ):
            self.assertIn(expected, html)

    def test_archived_report_is_explicitly_historical(self):
        self.assertEqual(
            report_terminal.report_context_label(archived=True),
            "HISTORICAL ARCHIVED REPORT — NOT CURRENT",
        )

    def test_report_terminal_has_no_hard_coded_pass_constant(self):
        source = Path(report_terminal.__file__).read_text(encoding="utf-8")
        self.assertNotIn('PIPELINE_STATUS = "PASS"', source)


if __name__ == "__main__":
    unittest.main()
