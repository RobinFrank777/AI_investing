"""Integrity and concurrency tests for the historical shadow publisher."""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from config import PROJECT_VERSION
from historical_shadow_publisher import (
    ARCHIVE_CONTRACT_VERSION,
    PUBLISHER_VERSION,
    VALIDATOR_VERSION,
    ArchiveAlreadyExistsError,
    ArchivePublicationConflictError,
    HistoricalShadowPublisher,
    SourceArtifactChangedError,
)


RUN_ID = "shadow-2026-08-13"
AS_OF_DATE = "2026-08-13"
SCORE_VERSION = "technical-score-v3.8.1-r1"
RISK_VERSION = "portfolio-risk-v3.8.1-r1"
SNAPSHOT_ID = "portfolio-2026-08-13"


class HistoricalShadowPublisherTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.archive_root = self.root / "archive" / "shadow"
        self.sources.mkdir()
        self._write_sources()

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _write_csv(path: Path, fieldnames, rows) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _write_sources(self) -> None:
        self._write_csv(
            self.sources / "candidates.csv",
            [
                "Ticker",
                "FinalScore",
                "TradeSignal",
                "CandidateRank",
                "Eligibility",
                "RunId",
                "AsOfDate",
                "ScoreModelVersion",
            ],
            [
                {
                    "Ticker": "NVDA",
                    "FinalScore": "82.5",
                    "TradeSignal": "BUY",
                    "CandidateRank": "1",
                    "Eligibility": "ELIGIBLE",
                    "RunId": RUN_ID,
                    "AsOfDate": AS_OF_DATE,
                    "ScoreModelVersion": SCORE_VERSION,
                }
            ],
        )
        self._write_csv(
            self.sources / "risk.csv",
            [
                "Ticker",
                "RiskStatus",
                "RiskModelVersion",
                "RiskAsOfDate",
                "PortfolioSnapshotId",
                "RunId",
                "ScoreModelVersion",
            ],
            [
                {
                    "Ticker": "NVDA",
                    "RiskStatus": "READY",
                    "RiskModelVersion": RISK_VERSION,
                    "RiskAsOfDate": AS_OF_DATE,
                    "PortfolioSnapshotId": SNAPSHOT_ID,
                    "RunId": RUN_ID,
                    "ScoreModelVersion": SCORE_VERSION,
                }
            ],
        )
        snapshot = {
            "RunId": RUN_ID,
            "AsOfDate": AS_OF_DATE,
            "ScoreModelVersion": SCORE_VERSION,
            "RiskModelVersion": RISK_VERSION,
            "PortfolioSnapshotId": SNAPSHOT_ID,
        }
        (self.sources / "portfolio_snapshot.json").write_text(
            json.dumps(snapshot) + "\n", encoding="utf-8"
        )
        report = "\n".join(
            [
                f"RunId: {RUN_ID}",
                f"AsOfDate: {AS_OF_DATE}",
                f"ScoreModelVersion: {SCORE_VERSION}",
                f"RiskModelVersion: {RISK_VERSION}",
                f"PortfolioSnapshotId: {SNAPSHOT_ID}",
                "",
            ]
        )
        (self.sources / "validation_report.md").write_text(report, encoding="utf-8")

    def _publish(self) -> Path:
        return HistoricalShadowPublisher().publish_archive(
            self.sources / "candidates.csv",
            self.sources / "risk.csv",
            self.sources / "portfolio_snapshot.json",
            self.sources / "validation_report.md",
            self.archive_root,
            RUN_ID,
            AS_OF_DATE,
            SCORE_VERSION,
            RISK_VERSION,
            SNAPSHOT_ID,
        )

    def test_source_mutation_fails_closed_and_cleans_temporary_archive(self):
        real_copyfile = shutil.copyfile

        def mutate_after_copy(source, destination):
            result = real_copyfile(source, destination)
            if Path(source).name == "candidates.csv":
                with Path(source).open("a", encoding="utf-8") as stream:
                    stream.write("MUTATION\n")
            return result

        with patch("historical_shadow_publisher.shutil.copyfile", side_effect=mutate_after_copy):
            with self.assertRaises(SourceArtifactChangedError):
                self._publish()

        self.assertFalse((self.archive_root / AS_OF_DATE).exists())
        self.assertEqual(list(self.archive_root.iterdir()), [])

    def test_manifest_contains_governance_fields_and_is_canonical(self):
        archive = self._publish()
        manifest_path = archive / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["ArchiveContractVersion"], ARCHIVE_CONTRACT_VERSION)
        self.assertEqual(manifest["PublisherVersion"], PUBLISHER_VERSION)
        self.assertEqual(manifest["ValidatorVersion"], VALIDATOR_VERSION)
        self.assertEqual(manifest["ValidatorResult"], "PASS")
        self.assertEqual(manifest["ProjectVersion"], PROJECT_VERSION)
        self.assertRegex(manifest["RepositoryCommit"], r"^[0-9a-f]{40}$")
        expected = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        ) + "\n"
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), expected)

    def test_concurrent_publication_has_exactly_one_winner(self):
        barrier = threading.Barrier(2)

        def publish_after_barrier():
            barrier.wait()
            try:
                return ("success", self._publish())
            except (ArchivePublicationConflictError, ArchiveAlreadyExistsError) as error:
                return ("failure", error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: publish_after_barrier(), range(2)))

        self.assertEqual([kind for kind, _ in results].count("success"), 1)
        self.assertEqual([kind for kind, _ in results].count("failure"), 1)
        self.assertTrue((self.archive_root / AS_OF_DATE).is_dir())

    def test_validation_failure_removes_only_own_temporary_directory(self):
        unrelated = self.archive_root / ".tmp_unrelated"
        unrelated.mkdir(parents=True)
        marker = unrelated / "keep.txt"
        marker.write_text("keep", encoding="utf-8")

        with patch.object(
            HistoricalShadowPublisher,
            "_validate_staged_archive",
            side_effect=ValueError("validation failed"),
        ):
            with self.assertRaisesRegex(ValueError, "validation failed"):
                self._publish()

        self.assertFalse((self.archive_root / AS_OF_DATE).exists())
        self.assertTrue(marker.is_file())
        remaining = {path.name for path in self.archive_root.iterdir()}
        self.assertEqual(remaining, {".tmp_unrelated"})


if __name__ == "__main__":
    unittest.main()
