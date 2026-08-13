"""TESTING-only fixtures for portfolio snapshot provenance construction."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from portfolio_snapshot_builder import (
    SNAPSHOT_CONTRACT_VERSION,
    PortfolioSnapshotBuilder,
    PortfolioSnapshotCollisionError,
    PortfolioSnapshotValidationError,
)


RUN_ID = "testing-run-20260813"
AS_OF_DATE = "2026-08-13"
SCORE_VERSION = "technical-score-v3.8.1-r1"
RISK_VERSION = "portfolio-risk-v3.8.1-r1"


class PortfolioSnapshotBuilderTests(unittest.TestCase):
    """All artifacts in this class are synthetic and labeled TESTING."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidates = self.root / "candidates.csv"
        self.risk = self.root / "risk.csv"
        self._write_candidates()
        self._write_risk([])

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _csv(path, columns, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def _write_candidates(self, *, run_id=RUN_ID, as_of_date=AS_OF_DATE):
        columns = (
            "Ticker",
            "RunId",
            "AsOfDate",
            "ScoreModelVersion",
            "CandidateRank",
            "FinalScore",
            "TradeSignal",
            "Eligibility",
            "PortfolioEligible",
            "ValidationStatus",
        )
        self._csv(
            self.candidates,
            columns,
            [
                {
                    "Ticker": "AAA",
                    "RunId": run_id,
                    "AsOfDate": as_of_date,
                    "ScoreModelVersion": SCORE_VERSION,
                    "CandidateRank": 1,
                    "FinalScore": 80,
                    "TradeSignal": "BUY",
                    "Eligibility": "ELIGIBLE",
                    "PortfolioEligible": True,
                    "ValidationStatus": "RISK_INPUT_PENDING",
                }
            ],
        )

    def _write_risk(self, rows):
        columns = (
            "Ticker",
            "RunId",
            "AsOfDate",
            "ScoreModelVersion",
            "RiskModelVersion",
            "PortfolioSnapshotId",
            "PortfolioAsOfDate",
            "RiskStatus",
        )
        self._csv(self.risk, columns, rows)

    @staticmethod
    def state(*, quantity="2", price="25", cash="50", total="100"):
        return {
            "Holdings": [
                {
                    "Ticker": "AAA",
                    "Quantity": quantity,
                    "ValuationPrice": price,
                    "ValuationDate": AS_OF_DATE,
                }
            ],
            "CashBalances": [{"Currency": "USD", "Amount": cash}],
            "TotalPortfolioValue": total,
            "SourceStatus": "VERIFIED",
            "ReconciliationStatus": "PASS",
            "ValuationConventionVersion": "testing-valuation-v1",
        }

    def build(self, **overrides):
        arguments = {
            "candidate_path": self.candidates,
            "risk_path": self.risk,
            "portfolio_state": self.state(),
            "run_id": RUN_ID,
            "as_of_date": AS_OF_DATE,
            "portfolio_as_of_date": AS_OF_DATE,
            "portfolio_source_id": "TESTING_SOURCE",
            "base_currency": "USD",
            "evidence_classification": "TESTING",
            "captured_timestamp": "2026-08-13T12:00:00+00:00",
        }
        arguments.update(overrides)
        return PortfolioSnapshotBuilder().build_snapshot(**arguments)

    def test_deterministic_id_and_state_hash(self):
        first = self.build()
        second = self.build(portfolio_state={
            **self.state(),
            "Holdings": list(reversed(self.state()["Holdings"])),
        })
        self.assertEqual(first["PortfolioStateHash"], second["PortfolioStateHash"])
        self.assertEqual(first["PortfolioSnapshotId"], second["PortfolioSnapshotId"])
        self.assertEqual(
            first["PortfolioSnapshotId"],
            f"portfolio-snapshot-20260813-{first['PortfolioStateHash'][:12]}",
        )
        self.assertEqual(first["PortfolioSnapshotContractVersion"], SNAPSHOT_CONTRACT_VERSION)
        self.assertEqual(first["EvidenceClassification"], "TESTING")
        self.assertEqual(first["PermittedAction"], "NO_ACTION")

    def test_state_change_changes_hash_and_id(self):
        first = self.build()
        second = self.build(portfolio_state=self.state(quantity="1", price="25", cash="75"))
        self.assertNotEqual(first["PortfolioStateHash"], second["PortfolioStateHash"])
        self.assertNotEqual(first["PortfolioSnapshotId"], second["PortfolioSnapshotId"])

    def test_candidate_and_risk_hashes_bind_exact_bytes(self):
        snapshot = self.build()
        self.assertEqual(snapshot["CandidateRowCount"], 1)
        self.assertEqual(snapshot["PortfolioEligibleCount"], 1)
        self.assertRegex(snapshot["CandidateArtifactHash"], r"^[0-9a-f]{64}$")
        self.assertRegex(snapshot["RiskArtifactHash"], r"^[0-9a-f]{64}$")
        self.assertIsNone(snapshot["RiskModelVersion"])

    def test_populated_risk_must_bind_snapshot_identity(self):
        preliminary = self.build()
        self._write_risk(
            [
                {
                    "Ticker": "AAA",
                    "RunId": RUN_ID,
                    "AsOfDate": AS_OF_DATE,
                    "ScoreModelVersion": SCORE_VERSION,
                    "RiskModelVersion": RISK_VERSION,
                    "PortfolioSnapshotId": preliminary["PortfolioSnapshotId"],
                    "PortfolioAsOfDate": AS_OF_DATE,
                    "RiskStatus": "READY",
                }
            ]
        )
        snapshot = self.build()
        self.assertEqual(snapshot["RiskModelVersion"], RISK_VERSION)
        self.assertNotEqual(snapshot["RiskArtifactHash"], preliminary["RiskArtifactHash"])

    def test_run_id_mismatch_fails_closed(self):
        with self.assertRaisesRegex(PortfolioSnapshotValidationError, "RUN_ID_MISMATCH"):
            self.build(run_id="testing-other-run")

    def test_as_of_date_mismatch_fails_closed(self):
        with self.assertRaisesRegex(PortfolioSnapshotValidationError, "AS_OF_DATE_MISMATCH"):
            self.build(as_of_date="2026-08-12", portfolio_as_of_date="2026-08-12")

    def test_future_portfolio_date_fails_closed(self):
        with self.assertRaisesRegex(PortfolioSnapshotValidationError, "FUTURE_PORTFOLIO_STATE"):
            self.build(portfolio_as_of_date="2026-08-14")

    def test_non_exact_float_and_failed_reconciliation_are_rejected(self):
        state = self.state()
        state["Holdings"][0]["Quantity"] = 2.0
        with self.assertRaisesRegex(PortfolioSnapshotValidationError, "INVALID_PORTFOLIO_VALUE"):
            self.build(portfolio_state=state)
        with self.assertRaisesRegex(
            PortfolioSnapshotValidationError, "PORTFOLIO_RECONCILIATION_FAILED"
        ):
            self.build(portfolio_state=self.state(total="101"))

    def test_risk_snapshot_mismatch_fails_closed(self):
        self._write_risk(
            [
                {
                    "Ticker": "AAA",
                    "RunId": RUN_ID,
                    "AsOfDate": AS_OF_DATE,
                    "ScoreModelVersion": SCORE_VERSION,
                    "RiskModelVersion": RISK_VERSION,
                    "PortfolioSnapshotId": "portfolio-snapshot-20260813-deadbeefdead",
                    "PortfolioAsOfDate": AS_OF_DATE,
                    "RiskStatus": "READY",
                }
            ]
        )
        with self.assertRaisesRegex(PortfolioSnapshotValidationError, "RISK_SNAPSHOT_MISMATCH"):
            self.build()

    def test_immutable_collision_rejected_without_overwrite(self):
        snapshot = self.build()
        output = self.root / "portfolio_snapshot.json"
        PortfolioSnapshotBuilder.publish_snapshot(snapshot, output)
        before = output.read_bytes()
        with self.assertRaises(PortfolioSnapshotCollisionError):
            PortfolioSnapshotBuilder.publish_snapshot(snapshot, output)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(json.loads(before)["EvidenceClassification"], "TESTING")


if __name__ == "__main__":
    unittest.main()
