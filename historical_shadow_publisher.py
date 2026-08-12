"""Publish immutable historical shadow archives outside the trading path."""

from __future__ import annotations

import hashlib
import ast
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any


ARCHIVE_FILENAMES = (
    "candidates.csv",
    "risk.csv",
    "portfolio_snapshot.json",
    "manifest.json",
    "validation_report.md",
)
SOURCE_FILENAMES = (
    "candidates.csv",
    "risk.csv",
    "portfolio_snapshot.json",
    "validation_report.md",
)
ARCHIVE_CONTRACT_VERSION = "V3.8.1-Phase6B8C"
PUBLISHER_VERSION = "historical-shadow-publisher-v3.8.1-r1"
VALIDATOR_VERSION = "historical-shadow-validator-v3.8.1-r1"


class ArchiveAlreadyExistsError(Exception):
    """Raised when immutable evidence already exists for an archive date."""

    pass


class ArchivePublicationConflictError(Exception):
    """Raised when another publisher owns the same date publication lock."""

    pass


class SourceArtifactChangedError(Exception):
    """Raised when source evidence changes while it is being published."""

    pass


class HistoricalShadowPublisher:
    """Copy, validate, and atomically publish one research-only archive."""

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _validate_date(cls, value: Any) -> str:
        text = cls._required_text(value, "as_of_date")
        try:
            parsed = date.fromisoformat(text)
        except ValueError as error:
            raise ValueError("as_of_date must use YYYY-MM-DD format") from error
        if parsed.isoformat() != text:
            raise ValueError("as_of_date must use YYYY-MM-DD format")
        return text

    @staticmethod
    def _validate_source(path_value: Any, label: str) -> Path:
        try:
            path = Path(path_value)
        except TypeError as error:
            raise ValueError(f"{label} must be a valid filesystem path") from error
        if not path.is_file():
            raise FileNotFoundError(f"{label} is missing or is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise PermissionError(f"{label} is not readable: {path}")
        try:
            with path.open("rb") as stream:
                stream.read(1)
        except OSError as error:
            raise PermissionError(f"{label} is not readable: {path}") from error
        return path

    @staticmethod
    def _prepare_archive_root(path_value: Any) -> Path:
        try:
            root = Path(path_value)
        except TypeError as error:
            raise ValueError("archive_root must be a valid filesystem path") from error
        if root.exists() and (not root.is_dir() or root.is_symlink()):
            raise ValueError(f"archive_root must be a real directory: {root}")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ValueError(f"archive_root cannot be created: {root}") from error
        if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
            raise PermissionError(f"archive_root is not readable and writable: {root}")
        return root

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _repository_commit() -> str:
        """Return the exact repository commit associated with this publisher run."""
        repository = Path(__file__).resolve().parent
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise ValueError("RepositoryCommit cannot be determined") from error
        commit = result.stdout.strip()
        if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
            raise ValueError("RepositoryCommit is not a full Git commit hash")
        return commit

    @staticmethod
    def _project_version() -> str:
        """Read PROJECT_VERSION from config.py without importing application code."""
        config_path = Path(__file__).resolve().parent / "config.py"
        try:
            module = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
        except (OSError, UnicodeError, SyntaxError) as error:
            raise ValueError("ProjectVersion cannot be determined") from error
        for statement in module.body:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if not any(isinstance(target, ast.Name) and target.id == "PROJECT_VERSION" for target in targets):
                continue
            try:
                value = ast.literal_eval(statement.value)
            except (ValueError, TypeError) as error:
                raise ValueError("ProjectVersion must be a literal string") from error
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise ValueError("ProjectVersion cannot be determined")

    @staticmethod
    def _acquire_lock(root: Path, as_of_date: str) -> Path:
        lock = root / f".publish_lock_{as_of_date}"
        try:
            lock.mkdir(mode=0o700)
        except FileExistsError as error:
            raise ArchivePublicationConflictError(
                f"another publication is active for {as_of_date}"
            ) from error
        except OSError as error:
            raise ArchivePublicationConflictError(
                f"publication lock cannot be created for {as_of_date}"
            ) from error
        return lock

    @staticmethod
    def _safe_cleanup_temporary(path: Path | None, root: Path) -> None:
        """Remove only this publisher's verified temporary directory."""
        if path is None or not path.exists():
            return
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        if (
            not path.is_dir()
            or path.is_symlink()
            or not path.name.startswith(".tmp_")
            or resolved_path.parent != resolved_root
        ):
            raise RuntimeError(f"refusing unsafe temporary cleanup: {path}")
        shutil.rmtree(path)

    @staticmethod
    def _validate_staged_archive(staged_archive: Path, archive_root: Path) -> None:
        """Run the established archive validator without creating a report artifact."""
        from historical_shadow_validator import HistoricalShadowValidator

        validator = HistoricalShadowValidator(staged_archive, output_path=None)
        validator.validate(check_immutability=True, archive_root=archive_root)

    def publish_archive(
        self,
        candidates_path: str | os.PathLike[str],
        risk_path: str | os.PathLike[str],
        portfolio_snapshot_path: str | os.PathLike[str],
        validation_report_path: str | os.PathLike[str],
        archive_root: str | os.PathLike[str],
        run_id: str,
        as_of_date: str,
        score_model_version: str,
        risk_model_version: str,
        portfolio_snapshot_id: str,
    ) -> Path:
        """Publish validated evidence and return its immutable archive directory.

        Source evidence is opened only for reading. Publication occurs only after
        the copied bytes pass the historical shadow archive validator.
        """
        metadata = {
            "RunId": self._required_text(run_id, "run_id"),
            "AsOfDate": self._validate_date(as_of_date),
            "ScoreModelVersion": self._required_text(
                score_model_version, "score_model_version"
            ),
            "RiskModelVersion": self._required_text(
                risk_model_version, "risk_model_version"
            ),
            "PortfolioSnapshotId": self._required_text(
                portfolio_snapshot_id, "portfolio_snapshot_id"
            ),
        }
        sources = {
            "candidates.csv": self._validate_source(candidates_path, "candidates_path"),
            "risk.csv": self._validate_source(risk_path, "risk_path"),
            "portfolio_snapshot.json": self._validate_source(
                portfolio_snapshot_path, "portfolio_snapshot_path"
            ),
            "validation_report.md": self._validate_source(
                validation_report_path, "validation_report_path"
            ),
        }
        root = self._prepare_archive_root(archive_root)
        target = root / metadata["AsOfDate"]
        if target.exists():
            raise ArchiveAlreadyExistsError(f"archive already exists: {target}")

        temporary_parent: Path | None = None
        publication_lock: Path | None = None
        try:
            publication_lock = self._acquire_lock(root, metadata["AsOfDate"])
            if target.exists():
                raise ArchiveAlreadyExistsError(f"archive already exists: {target}")
            temporary_parent = Path(tempfile.mkdtemp(prefix=".tmp_", dir=root))
            staged_archive = temporary_parent / metadata["AsOfDate"]
            staged_archive.mkdir()

            source_hashes_before = {
                filename: self._sha256(source) for filename, source in sources.items()
            }
            for filename, source in sources.items():
                shutil.copyfile(source, staged_archive / filename)
            source_hashes_after = {
                filename: self._sha256(source) for filename, source in sources.items()
            }
            copied_hashes = {
                filename: self._sha256(staged_archive / filename) for filename in sources
            }
            changed = sorted(
                filename
                for filename in sources
                if source_hashes_before[filename] != source_hashes_after[filename]
                or source_hashes_before[filename] != copied_hashes[filename]
            )
            if changed:
                raise SourceArtifactChangedError(
                    "source evidence changed during publication: " + ", ".join(changed)
                )

            manifest = {
                **metadata,
                "ArchiveContractVersion": ARCHIVE_CONTRACT_VERSION,
                "PublisherVersion": PUBLISHER_VERSION,
                "ValidatorVersion": VALIDATOR_VERSION,
                "ValidatorResult": "PASS",
                "RepositoryCommit": self._repository_commit(),
                "ProjectVersion": self._project_version(),
                "CandidateArtifactHash": copied_hashes["candidates.csv"],
                "RiskArtifactHash": copied_hashes["risk.csv"],
                "PortfolioSnapshotHash": copied_hashes["portfolio_snapshot.json"],
                "ValidationReportHash": copied_hashes["validation_report.md"],
                "Files": list(ARCHIVE_FILENAMES),
            }
            (staged_archive / "manifest.json").write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                    separators=(",", ": "),
                )
                + "\n",
                encoding="utf-8",
            )

            self._validate_staged_archive(staged_archive, root)
            if target.exists():
                raise ArchiveAlreadyExistsError(f"archive already exists: {target}")
            staged_archive.rename(target)
            return target
        finally:
            self._safe_cleanup_temporary(temporary_parent, root)
            if publication_lock is not None and publication_lock.exists():
                publication_lock.rmdir()
