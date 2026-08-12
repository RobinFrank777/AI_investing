"""Validate immutable, non-production historical shadow archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "shadow_validation_report.json"

REQUIRED_FILES = frozenset(
    {
        "candidates.csv",
        "risk.csv",
        "portfolio_snapshot.json",
        "manifest.json",
        "validation_report.md",
    }
)
HASH_FIELDS = {
    "candidates.csv": "CandidateArtifactHash",
    "risk.csv": "RiskArtifactHash",
    "portfolio_snapshot.json": "PortfolioSnapshotHash",
    "validation_report.md": "ValidationReportHash",
}
CANDIDATE_COLUMNS = (
    "Ticker",
    "FinalScore",
    "TradeSignal",
    "CandidateRank",
    "Eligibility",
    "RunId",
    "AsOfDate",
    "ScoreModelVersion",
)
RISK_COLUMNS = (
    "Ticker",
    "RiskStatus",
    "RiskModelVersion",
    "RiskAsOfDate",
    "PortfolioSnapshotId",
    "RunId",
    "ScoreModelVersion",
)
METADATA_FIELDS = (
    "RunId",
    "AsOfDate",
    "ScoreModelVersion",
    "RiskModelVersion",
)
ALLOWED_RISK_STATES = frozenset({"READY", "PENDING", "BLOCKED", "FAILED"})


class HistoricalShadowValidationError(ValueError):
    """Fail-closed archive validation error carrying a stable reason code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


class HistoricalShadowValidator:
    """Validate one archive and optionally detect cross-archive immutability."""

    def __init__(self, archive_directory, output_path=DEFAULT_OUTPUT_PATH):
        self.archive_directory = Path(archive_directory)
        self.output_path = Path(output_path) if output_path is not None else None

    def _path(self, name: str) -> Path:
        return self.archive_directory / name

    def _required_file_validation(self) -> None:
        if not self.archive_directory.is_dir():
            raise HistoricalShadowValidationError(
                "ARCHIVE_FILE_MISSING", f"archive directory not found: {self.archive_directory}"
            )
        missing = sorted(name for name in REQUIRED_FILES if not self._path(name).is_file())
        if missing:
            raise HistoricalShadowValidationError(
                "ARCHIVE_FILE_MISSING", "missing required files: " + ", ".join(missing)
            )

    def _load_manifest(self) -> dict:
        try:
            manifest = json.loads(self._path("manifest.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeError) as error:
            raise HistoricalShadowValidationError(
                "INVALID_MANIFEST", f"manifest cannot be read: {error}"
            ) from error
        if not isinstance(manifest, dict):
            raise HistoricalShadowValidationError("INVALID_MANIFEST", "manifest must be an object")
        listed = manifest.get("Files")
        if not isinstance(listed, list) or set(listed) != REQUIRED_FILES:
            raise HistoricalShadowValidationError(
                "INVALID_MANIFEST", "Files must list the complete archive contract"
            )
        for field in (*METADATA_FIELDS, "PortfolioSnapshotId", *HASH_FIELDS.values()):
            if not _normalized_text(manifest.get(field)):
                raise HistoricalShadowValidationError(
                    "INVALID_MANIFEST", f"manifest missing {field}"
                )
        return manifest

    def _validate_hashes(self, manifest: dict) -> None:
        for filename, field in HASH_FIELDS.items():
            expected = _normalized_text(manifest[field]).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise HistoricalShadowValidationError(
                    "INVALID_MANIFEST", f"{field} must be a SHA-256 digest"
                )
            actual = _sha256(self._path(filename))
            if actual != expected:
                raise HistoricalShadowValidationError(
                    "ARCHIVE_HASH_MISMATCH", f"{filename} hash does not match {field}"
                )

    def _load_csv(self, name: str, error_code: str) -> pd.DataFrame:
        try:
            return pd.read_csv(self._path(name))
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeError) as error:
            raise HistoricalShadowValidationError(
                error_code, f"{name} cannot be read: {error}"
            ) from error

    def _validate_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in CANDIDATE_COLUMNS if column not in candidates]
        if missing:
            raise HistoricalShadowValidationError(
                "INVALID_CANDIDATE_ARCHIVE", "missing fields: " + ", ".join(missing)
            )
        frame = candidates.copy(deep=True)
        if frame.empty:
            return frame
        frame["Ticker"] = frame.Ticker.fillna("").astype(str).str.strip().str.upper()
        if (frame.Ticker == "").any():
            raise HistoricalShadowValidationError(
                "INVALID_CANDIDATE_ARCHIVE", "missing Ticker"
            )
        if frame.Ticker.duplicated().any():
            raise HistoricalShadowValidationError(
                "INVALID_CANDIDATE_ARCHIVE", "duplicate Ticker"
            )
        frame["RunId"] = frame.RunId.fillna("").astype(str).str.strip()
        if (frame.RunId == "").any():
            raise HistoricalShadowValidationError(
                "INVALID_CANDIDATE_ARCHIVE", "missing RunId"
            )
        frame["FinalScore"] = pd.to_numeric(frame.FinalScore, errors="coerce")
        if frame.FinalScore.isna().any() or not np.isfinite(frame.FinalScore).all():
            raise HistoricalShadowValidationError(
                "INVALID_CANDIDATE_ARCHIVE", "non-finite FinalScore"
            )
        frame["Eligibility"] = frame.Eligibility.fillna("").astype(str).str.strip().str.upper()
        frame["TradeSignal"] = frame.TradeSignal.fillna("").astype(str).str.strip().str.upper()
        promoted = (frame.Eligibility == "ELIGIBLE") & (frame.TradeSignal != "BUY")
        if promoted.any():
            raise HistoricalShadowValidationError(
                "INVALID_CANDIDATE_ARCHIVE", "only BUY may be ELIGIBLE"
            )
        return frame

    def _validate_risk(self, risk: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in RISK_COLUMNS if column not in risk]
        if missing:
            raise HistoricalShadowValidationError(
                "INVALID_RISK_ARCHIVE", "missing fields: " + ", ".join(missing)
            )
        frame = risk.copy(deep=True)
        if frame.empty:
            return frame
        frame["Ticker"] = frame.Ticker.fillna("").astype(str).str.strip().str.upper()
        if (frame.Ticker == "").any() or frame.Ticker.duplicated().any():
            raise HistoricalShadowValidationError(
                "INVALID_RISK_ARCHIVE", "missing or duplicate Ticker"
            )
        frame["RiskStatus"] = frame.RiskStatus.fillna("").astype(str).str.strip().str.upper()
        invalid = sorted(set(frame.RiskStatus) - ALLOWED_RISK_STATES)
        if invalid:
            raise HistoricalShadowValidationError(
                "INVALID_RISK_ARCHIVE", "invalid RiskStatus: " + ", ".join(invalid)
            )
        return frame

    def _load_portfolio_snapshot(self) -> dict:
        try:
            snapshot = json.loads(
                self._path("portfolio_snapshot.json").read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError, UnicodeError) as error:
            raise HistoricalShadowValidationError(
                "METADATA_MISMATCH", f"portfolio snapshot cannot be read: {error}"
            ) from error
        if not isinstance(snapshot, dict):
            raise HistoricalShadowValidationError(
                "METADATA_MISMATCH", "portfolio snapshot must be an object"
            )
        return snapshot

    def _load_report_metadata(self) -> dict:
        try:
            text = self._path("validation_report.md").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise HistoricalShadowValidationError(
                "METADATA_MISMATCH", f"validation report cannot be read: {error}"
            ) from error
        metadata = {}
        for field in (*METADATA_FIELDS, "PortfolioSnapshotId"):
            pattern = rf"(?mi)^\s*(?:[-*]\s*)?{re.escape(field)}\s*:\s*`?([^`\r\n]+?)`?\s*$"
            match = re.search(pattern, text)
            if match:
                metadata[field] = match.group(1).strip()
        return metadata

    @staticmethod
    def _unique_metadata(frame: pd.DataFrame, field: str, label: str) -> str | None:
        if frame.empty:
            return None
        if field not in frame:
            raise HistoricalShadowValidationError(
                "METADATA_MISMATCH", f"{label} missing {field}"
            )
        values = [_normalized_text(value) for value in frame[field].unique().tolist()]
        if len(values) != 1 or not values[0]:
            raise HistoricalShadowValidationError(
                "METADATA_MISMATCH", f"{label} has mixed or missing {field}"
            )
        return values[0]

    def _validate_metadata(
        self,
        manifest: dict,
        candidates: pd.DataFrame,
        risk: pd.DataFrame,
        snapshot: dict,
        report_metadata: dict,
    ) -> None:
        expected = {field: _normalized_text(manifest[field]) for field in METADATA_FIELDS}
        expected["PortfolioSnapshotId"] = _normalized_text(manifest["PortfolioSnapshotId"])
        if self.archive_directory.name != expected["AsOfDate"]:
            raise HistoricalShadowValidationError(
                "METADATA_MISMATCH", "archive directory does not match AsOfDate"
            )

        candidate_fields = ("RunId", "AsOfDate", "ScoreModelVersion")
        for field in candidate_fields:
            actual = self._unique_metadata(candidates, field, "candidates.csv")
            if actual is not None and actual != expected[field]:
                raise HistoricalShadowValidationError(
                    "METADATA_MISMATCH", f"candidates.csv {field} conflicts with manifest"
                )

        risk_field_map = {
            "RunId": "RunId",
            "AsOfDate": "RiskAsOfDate",
            "ScoreModelVersion": "ScoreModelVersion",
            "RiskModelVersion": "RiskModelVersion",
            "PortfolioSnapshotId": "PortfolioSnapshotId",
        }
        for metadata_field, csv_field in risk_field_map.items():
            actual = self._unique_metadata(risk, csv_field, "risk.csv")
            if actual is not None and actual != expected[metadata_field]:
                raise HistoricalShadowValidationError(
                    "METADATA_MISMATCH", f"risk.csv {csv_field} conflicts with manifest"
                )

        for field in (*METADATA_FIELDS, "PortfolioSnapshotId"):
            if _normalized_text(snapshot.get(field)) != expected[field]:
                raise HistoricalShadowValidationError(
                    "METADATA_MISMATCH", f"portfolio_snapshot.json {field} conflicts with manifest"
                )
            if _normalized_text(report_metadata.get(field)) != expected[field]:
                raise HistoricalShadowValidationError(
                    "METADATA_MISMATCH", f"validation_report.md {field} conflicts with manifest"
                )

    @staticmethod
    def _validate_join(candidates: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
        eligible = candidates.loc[candidates.Eligibility == "ELIGIBLE"].copy()
        if eligible.empty:
            return eligible
        risk_tickers = set(risk.Ticker)
        missing = sorted(set(eligible.Ticker) - risk_tickers)
        if missing:
            raise HistoricalShadowValidationError(
                "MISSING_RISK", "eligible candidates without risk: " + ", ".join(missing)
            )
        return eligible

    @staticmethod
    def _result(manifest: dict, candidates: pd.DataFrame, risk: pd.DataFrame) -> dict:
        eligible_count = int((candidates.Eligibility == "ELIGIBLE").sum())
        counts = risk.RiskStatus.value_counts().to_dict() if not risk.empty else {}
        blocked_count = int(counts.get("BLOCKED", 0) + counts.get("FAILED", 0))
        if blocked_count:
            scenario = "RISK_BLOCKED"
        elif eligible_count == 0:
            scenario = "ZERO_ELIGIBLE"
        elif eligible_count == 1:
            scenario = "SINGLE_ELIGIBLE"
        else:
            scenario = "MULTIPLE_ELIGIBLE"
        return {
            "RunId": _normalized_text(manifest["RunId"]),
            "AsOfDate": _normalized_text(manifest["AsOfDate"]),
            "candidate_count": int(len(candidates)),
            "eligible_count": eligible_count,
            "risk_ready": int(counts.get("READY", 0)),
            "risk_pending": int(counts.get("PENDING", 0)),
            "risk_blocked": blocked_count,
            "scenario": scenario,
            "status": "PASS",
        }

    def validate_archive_immutability(self, archive_root=None) -> bool:
        """Reject two manifests with the same RunId/AsOfDate and different hashes."""
        root = Path(archive_root) if archive_root is not None else self.archive_directory.parent
        manifests = sorted(root.rglob("manifest.json")) if root.exists() else []
        identities = {}
        for path in manifests:
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeError) as error:
                raise HistoricalShadowValidationError(
                    "IMMUTABILITY_VIOLATION", f"cannot inspect {path}: {error}"
                ) from error
            run_id = _normalized_text(manifest.get("RunId"))
            as_of_date = _normalized_text(manifest.get("AsOfDate"))
            candidate_hash = _normalized_text(manifest.get("CandidateArtifactHash"))
            risk_hash = _normalized_text(manifest.get("RiskArtifactHash"))
            if not all((run_id, as_of_date, candidate_hash, risk_hash)):
                raise HistoricalShadowValidationError(
                    "IMMUTABILITY_VIOLATION", f"incomplete immutable identity in {path}"
                )
            identity = (run_id, as_of_date)
            fingerprint = (candidate_hash, risk_hash)
            previous = identities.get(identity)
            if previous is not None and previous != fingerprint:
                raise HistoricalShadowValidationError(
                    "IMMUTABILITY_VIOLATION",
                    f"{run_id}/{as_of_date} has multiple artifact hashes",
                )
            identities[identity] = fingerprint
        return True

    def validate(self, *, check_immutability=True, archive_root=None) -> dict:
        """Validate the archive and return its deterministic summary."""
        self._required_file_validation()
        manifest = self._load_manifest()
        self._validate_hashes(manifest)
        candidates = self._validate_candidates(
            self._load_csv("candidates.csv", "INVALID_CANDIDATE_ARCHIVE")
        )
        risk = self._validate_risk(self._load_csv("risk.csv", "INVALID_RISK_ARCHIVE"))
        snapshot = self._load_portfolio_snapshot()
        report_metadata = self._load_report_metadata()
        self._validate_metadata(manifest, candidates, risk, snapshot, report_metadata)
        self._validate_join(candidates, risk)
        if check_immutability:
            self.validate_archive_immutability(archive_root)
        return self._result(manifest, candidates, risk)

    def validate_and_write(self, *, check_immutability=True, archive_root=None) -> dict:
        result = self.validate(
            check_immutability=check_immutability,
            archive_root=archive_root,
        )
        if self.output_path is None:
            raise ValueError("output_path is required to write the validation result")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_directory", help="archive/shadow/YYYY-MM-DD directory")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--archive-root")
    args = parser.parse_args(argv)
    validator = HistoricalShadowValidator(args.archive_directory, args.output)
    result = validator.validate_and_write(archive_root=args.archive_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
