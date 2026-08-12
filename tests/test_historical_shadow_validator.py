import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from historical_shadow_validator import (
    HistoricalShadowValidationError,
    HistoricalShadowValidator,
    REQUIRED_FILES,
)


RUN_ID = "A001"
AS_OF_DATE = "2026-08-11"
SCORE_VERSION = "technical-score-v3.8.1-r1"
RISK_VERSION = "portfolio-risk-v3.8.1-r1"
SNAPSHOT_ID = "portfolio-001"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate(ticker="NVDA", eligibility="ELIGIBLE", rank=1):
    return {
        "Ticker": ticker,
        "FinalScore": 80.0,
        "TradeSignal": "BUY" if eligibility == "ELIGIBLE" else "WATCH",
        "CandidateRank": rank,
        "Eligibility": eligibility,
        "RunId": RUN_ID,
        "AsOfDate": AS_OF_DATE,
        "ScoreModelVersion": SCORE_VERSION,
    }


def risk(ticker="NVDA", status="READY", run_id=RUN_ID):
    return {
        "Ticker": ticker,
        "RiskStatus": status,
        "RiskModelVersion": RISK_VERSION,
        "RiskAsOfDate": AS_OF_DATE,
        "PortfolioSnapshotId": SNAPSHOT_ID,
        "RunId": run_id,
        "ScoreModelVersion": SCORE_VERSION,
    }


def build_archive(root, candidates=None, risks=None, *, directory_name=AS_OF_DATE):
    archive = Path(root) / directory_name
    archive.mkdir(parents=True)
    candidates = [candidate()] if candidates is None else candidates
    risks = [risk()] if risks is None else risks
    pd.DataFrame(candidates, columns=candidate().keys()).to_csv(
        archive / "candidates.csv", index=False
    )
    pd.DataFrame(risks, columns=risk().keys()).to_csv(archive / "risk.csv", index=False)
    snapshot = {
        "RunId": RUN_ID,
        "AsOfDate": AS_OF_DATE,
        "ScoreModelVersion": SCORE_VERSION,
        "RiskModelVersion": RISK_VERSION,
        "PortfolioSnapshotId": SNAPSHOT_ID,
    }
    (archive / "portfolio_snapshot.json").write_text(
        json.dumps(snapshot, sort_keys=True), encoding="utf-8"
    )
    report = "\n".join(
        [
            "# Validation Report",
            f"RunId: {RUN_ID}",
            f"AsOfDate: {AS_OF_DATE}",
            f"ScoreModelVersion: {SCORE_VERSION}",
            f"RiskModelVersion: {RISK_VERSION}",
            f"PortfolioSnapshotId: {SNAPSHOT_ID}",
        ]
    ) + "\n"
    (archive / "validation_report.md").write_text(report, encoding="utf-8")
    manifest = {
        "Files": sorted(REQUIRED_FILES),
        "RunId": RUN_ID,
        "AsOfDate": AS_OF_DATE,
        "ScoreModelVersion": SCORE_VERSION,
        "RiskModelVersion": RISK_VERSION,
        "PortfolioSnapshotId": SNAPSHOT_ID,
        "CandidateArtifactHash": sha256(archive / "candidates.csv"),
        "RiskArtifactHash": sha256(archive / "risk.csv"),
        "PortfolioSnapshotHash": sha256(archive / "portfolio_snapshot.json"),
        "ValidationReportHash": sha256(archive / "validation_report.md"),
    }
    (archive / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return archive


class HistoricalShadowValidatorTests(unittest.TestCase):
    def assert_code(self, code, callable_):
        with self.assertRaises(HistoricalShadowValidationError) as context:
            callable_()
        self.assertEqual(context.exception.code, code)

    def test_valid_archive_passes_and_writes_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary)
            output = Path(temporary) / "result.json"
            result = HistoricalShadowValidator(archive, output).validate_and_write()
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["scenario"], "SINGLE_ELIGIBLE")
            self.assertEqual(json.loads(output.read_text()), result)

    def test_missing_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary)
            (archive / "manifest.json").unlink()
            self.assert_code(
                "ARCHIVE_FILE_MISSING", HistoricalShadowValidator(archive).validate
            )

    def test_hash_error_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary)
            with (archive / "candidates.csv").open("a", encoding="utf-8") as stream:
                stream.write("tampered\n")
            self.assert_code(
                "ARCHIVE_HASH_MISMATCH", HistoricalShadowValidator(archive).validate
            )

    def test_metadata_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary, risks=[risk(run_id="A002")])
            self.assert_code(
                "METADATA_MISMATCH", HistoricalShadowValidator(archive).validate
            )

    def test_duplicate_ticker_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary, candidates=[candidate(), candidate(" nvda ", rank=2)])
            self.assert_code(
                "INVALID_CANDIDATE_ARCHIVE", HistoricalShadowValidator(archive).validate
            )

    def test_missing_risk_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary, risks=[])
            self.assert_code("MISSING_RISK", HistoricalShadowValidator(archive).validate)

    def test_invalid_risk_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary, risks=[risk(status="UNKNOWN")])
            self.assert_code(
                "INVALID_RISK_ARCHIVE", HistoricalShadowValidator(archive).validate
            )

    def test_zero_eligible_scenario(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(
                temporary,
                candidates=[candidate(eligibility="INELIGIBLE")],
                risks=[],
            )
            result = HistoricalShadowValidator(archive).validate()
            self.assertEqual(result["scenario"], "ZERO_ELIGIBLE")
            self.assertEqual(result["eligible_count"], 0)

    def test_single_eligible_scenario(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary)
            result = HistoricalShadowValidator(archive).validate()
            self.assertEqual(result["scenario"], "SINGLE_ELIGIBLE")
            self.assertEqual(result["eligible_count"], 1)

    def test_multiple_eligible_scenario(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(
                temporary,
                candidates=[candidate("NVDA", rank=1), candidate("AMD", rank=2)],
                risks=[risk("NVDA"), risk("AMD")],
            )
            result = HistoricalShadowValidator(archive).validate()
            self.assertEqual(result["scenario"], "MULTIPLE_ELIGIBLE")
            self.assertEqual(result["eligible_count"], 2)

    def test_blocked_risk_scenario_and_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary, risks=[risk(status="FAILED")])
            result = HistoricalShadowValidator(archive).validate()
            self.assertEqual(result["scenario"], "RISK_BLOCKED")
            self.assertEqual(result["risk_blocked"], 1)

    def test_immutability_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = build_archive(root / "first")
            second = build_archive(root / "second")
            manifest_path = second / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["CandidateArtifactHash"] = "f" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            validator = HistoricalShadowValidator(first)
            self.assert_code(
                "IMMUTABILITY_VIOLATION",
                lambda: validator.validate_archive_immutability(root),
            )

    def test_input_archive_files_are_not_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = build_archive(temporary)
            before = {path.name: path.read_bytes() for path in archive.iterdir()}
            HistoricalShadowValidator(archive).validate()
            after = {path.name: path.read_bytes() for path in archive.iterdir()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
