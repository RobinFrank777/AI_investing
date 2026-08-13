"""Build immutable, research-only portfolio snapshot provenance artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


SNAPSHOT_CONTRACT_VERSION = "portfolio-snapshot-v3.8.1-r1"
BUILDER_VERSION = "portfolio-snapshot-builder-v3.8.1-r1"
ALLOWED_EVIDENCE_CLASSIFICATIONS = frozenset({"REAL_HISTORICAL", "TESTING"})

CANDIDATE_REQUIRED_COLUMNS = (
    "Ticker",
    "RunId",
    "AsOfDate",
    "ScoreModelVersion",
    "PortfolioEligible",
)
RISK_REQUIRED_COLUMNS = (
    "Ticker",
    "RunId",
    "AsOfDate",
    "ScoreModelVersion",
    "RiskModelVersion",
    "PortfolioSnapshotId",
    "PortfolioAsOfDate",
)


class PortfolioSnapshotValidationError(ValueError):
    """Fail-closed snapshot validation error with a stable reason code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class PortfolioSnapshotCollisionError(FileExistsError):
    """Raised when immutable snapshot publication would overwrite a file."""

    pass


def _fail(code: str, message: str) -> None:
    raise PortfolioSnapshotValidationError(code, message)


class PortfolioSnapshotBuilder:
    """Validate evidence and construct deterministic portfolio provenance."""

    @staticmethod
    def _required_text(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            _fail("SNAPSHOT_METADATA_MISSING", f"{field} must be a non-empty string")
        return value.strip()

    @classmethod
    def _iso_date(cls, value: Any, field: str) -> str:
        text = cls._required_text(value, field)
        try:
            parsed = date.fromisoformat(text)
        except ValueError as error:
            raise PortfolioSnapshotValidationError(
                "SNAPSHOT_DATE_INVALID", f"{field} must use YYYY-MM-DD"
            ) from error
        if parsed.isoformat() != text:
            _fail("SNAPSHOT_DATE_INVALID", f"{field} must use YYYY-MM-DD")
        return text

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError as error:
            raise PortfolioSnapshotValidationError(
                "ARTIFACT_UNREADABLE", f"cannot hash {path}"
            ) from error
        return digest.hexdigest()

    @staticmethod
    def _read_csv(path_value: Any, label: str, required_columns: Sequence[str]):
        try:
            path = Path(path_value)
        except TypeError as error:
            raise PortfolioSnapshotValidationError(
                "ARTIFACT_UNREADABLE", f"{label} path is invalid"
            ) from error
        if not path.is_file() or path.is_symlink():
            _fail("ARTIFACT_UNREADABLE", f"{label} must be a regular file: {path}")
        before = PortfolioSnapshotBuilder._sha256(path)
        try:
            with path.open("r", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                columns = tuple(reader.fieldnames or ())
                rows = list(reader)
        except (OSError, UnicodeError, csv.Error) as error:
            raise PortfolioSnapshotValidationError(
                "ARTIFACT_UNREADABLE", f"cannot parse {label}: {path}"
            ) from error
        missing = [column for column in required_columns if column not in columns]
        if missing:
            _fail("ARTIFACT_SCHEMA_INVALID", f"{label} missing: {', '.join(missing)}")
        after = PortfolioSnapshotBuilder._sha256(path)
        if before != after:
            _fail("ARTIFACT_CHANGED", f"{label} changed while being read")
        return path, rows, before

    @staticmethod
    def _single(rows: Sequence[Mapping[str, str]], field: str, label: str) -> str:
        values = {str(row.get(field, "")).strip() for row in rows}
        if len(values) != 1 or not next(iter(values), ""):
            _fail("SNAPSHOT_METADATA_MIXED", f"{label} has mixed or missing {field}")
        return next(iter(values))

    @staticmethod
    def _boolean(value: Any, field: str) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().upper()
        if normalized == "TRUE":
            return True
        if normalized == "FALSE":
            return False
        _fail("CANDIDATE_ARTIFACT_INVALID", f"invalid {field}")

    @staticmethod
    def _decimal(value: Any, field: str, *, non_negative: bool = True) -> str:
        if isinstance(value, bool) or isinstance(value, float):
            _fail("INVALID_PORTFOLIO_VALUE", f"{field} must use an exact decimal value")
        try:
            number = Decimal(str(value).strip())
        except (InvalidOperation, AttributeError) as error:
            raise PortfolioSnapshotValidationError(
                "INVALID_PORTFOLIO_VALUE", f"{field} is not decimal"
            ) from error
        if not number.is_finite() or (non_negative and number < 0):
            _fail("INVALID_PORTFOLIO_VALUE", f"{field} is invalid")
        normalized = format(number.normalize(), "f")
        return "0" if Decimal(normalized) == 0 else normalized

    @classmethod
    def _canonical_state(
        cls,
        portfolio_state: Mapping[str, Any],
        *,
        portfolio_as_of_date: str,
        portfolio_source_id: str,
        base_currency: str,
    ) -> dict:
        if not isinstance(portfolio_state, Mapping):
            _fail("INVALID_PORTFOLIO_VALUE", "portfolio_state must be an object")
        holdings = portfolio_state.get("Holdings")
        cash = portfolio_state.get("CashBalances")
        if not isinstance(holdings, list) or not isinstance(cash, list):
            _fail("INVALID_PORTFOLIO_VALUE", "Holdings and CashBalances must be lists")

        canonical_holdings = []
        tickers = set()
        for index, holding in enumerate(holdings):
            if not isinstance(holding, Mapping):
                _fail("INVALID_PORTFOLIO_VALUE", f"Holdings[{index}] must be an object")
            ticker = cls._required_text(holding.get("Ticker"), f"Holdings[{index}].Ticker").upper()
            if ticker in tickers:
                _fail("DUPLICATE_HOLDING", f"duplicate Ticker {ticker}")
            tickers.add(ticker)
            valuation_date = cls._iso_date(
                holding.get("ValuationDate"), f"Holdings[{index}].ValuationDate"
            )
            if valuation_date > portfolio_as_of_date:
                _fail("FUTURE_PORTFOLIO_STATE", f"{ticker} valuation is future-dated")
            canonical_holdings.append(
                {
                    "Ticker": ticker,
                    "Quantity": cls._decimal(
                        holding.get("Quantity"), f"Holdings[{index}].Quantity"
                    ),
                    "ValuationPrice": cls._decimal(
                        holding.get("ValuationPrice"),
                        f"Holdings[{index}].ValuationPrice",
                    ),
                    "ValuationDate": valuation_date,
                }
            )

        canonical_cash = []
        currencies = set()
        for index, balance in enumerate(cash):
            if not isinstance(balance, Mapping):
                _fail("INVALID_PORTFOLIO_VALUE", f"CashBalances[{index}] must be an object")
            currency = cls._required_text(
                balance.get("Currency"), f"CashBalances[{index}].Currency"
            ).upper()
            if currency in currencies:
                _fail("INVALID_PORTFOLIO_VALUE", f"duplicate cash currency {currency}")
            if currency != base_currency:
                _fail("INVALID_PORTFOLIO_VALUE", "first contract requires base-currency cash")
            currencies.add(currency)
            canonical_cash.append(
                {
                    "Currency": currency,
                    "Amount": cls._decimal(
                        balance.get("Amount"), f"CashBalances[{index}].Amount"
                    ),
                }
            )

        source_status = cls._required_text(
            portfolio_state.get("SourceStatus"), "SourceStatus"
        ).upper()
        reconciliation_status = cls._required_text(
            portfolio_state.get("ReconciliationStatus"), "ReconciliationStatus"
        ).upper()
        if source_status != "VERIFIED" or reconciliation_status != "PASS":
            _fail("PORTFOLIO_RECONCILIATION_FAILED", "source and reconciliation must pass")
        valuation_version = cls._required_text(
            portfolio_state.get("ValuationConventionVersion"),
            "ValuationConventionVersion",
        )
        total = cls._decimal(portfolio_state.get("TotalPortfolioValue"), "TotalPortfolioValue")
        calculated = sum(
            Decimal(row["Quantity"]) * Decimal(row["ValuationPrice"])
            for row in canonical_holdings
        ) + sum(Decimal(row["Amount"]) for row in canonical_cash)
        if Decimal(total) != calculated:
            _fail("PORTFOLIO_RECONCILIATION_FAILED", "TotalPortfolioValue does not reconcile")

        return {
            "PortfolioSnapshotContractVersion": SNAPSHOT_CONTRACT_VERSION,
            "PortfolioAsOfDate": portfolio_as_of_date,
            "PortfolioSourceId": portfolio_source_id,
            "BaseCurrency": base_currency,
            "ValuationConventionVersion": valuation_version,
            "Holdings": sorted(canonical_holdings, key=lambda row: row["Ticker"]),
            "CashBalances": sorted(canonical_cash, key=lambda row: row["Currency"]),
            "TotalPortfolioValue": total,
            "SourceStatus": source_status,
            "ReconciliationStatus": reconciliation_status,
        }

    @staticmethod
    def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
        return (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _repository_commit() -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).resolve().parent,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise PortfolioSnapshotValidationError(
                "REPOSITORY_PROVENANCE_UNAVAILABLE", "cannot determine repository commit"
            ) from error
        commit = result.stdout.strip().lower()
        if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
            _fail("REPOSITORY_PROVENANCE_UNAVAILABLE", "invalid repository commit")
        return commit

    @classmethod
    def _validate_risk_rows(
        cls,
        rows: Sequence[Mapping[str, str]],
        *,
        run_id: str,
        as_of_date: str,
        score_model_version: str,
        portfolio_snapshot_id: str,
        portfolio_as_of_date: str,
    ) -> str | None:
        if not rows:
            return None
        expected = {
            "RunId": run_id,
            "AsOfDate": as_of_date,
            "ScoreModelVersion": score_model_version,
            "PortfolioSnapshotId": portfolio_snapshot_id,
            "PortfolioAsOfDate": portfolio_as_of_date,
        }
        for field, value in expected.items():
            if cls._single(rows, field, "risk artifact") != value:
                _fail("RISK_SNAPSHOT_MISMATCH", f"risk {field} conflicts with snapshot")
        return cls._single(rows, "RiskModelVersion", "risk artifact")

    def build_snapshot(
        self,
        candidate_path: str | os.PathLike[str],
        risk_path: str | os.PathLike[str],
        portfolio_state: Mapping[str, Any],
        *,
        run_id: str,
        as_of_date: str,
        portfolio_as_of_date: str,
        portfolio_source_id: str,
        base_currency: str,
        evidence_classification: str,
        captured_timestamp: str | None = None,
    ) -> dict:
        """Return validated snapshot provenance without writing or taking action."""
        run_id = self._required_text(run_id, "RunId")
        as_of_date = self._iso_date(as_of_date, "AsOfDate")
        portfolio_as_of_date = self._iso_date(portfolio_as_of_date, "PortfolioAsOfDate")
        if portfolio_as_of_date > as_of_date:
            _fail("FUTURE_PORTFOLIO_STATE", "PortfolioAsOfDate exceeds AsOfDate")
        source_id = self._required_text(portfolio_source_id, "PortfolioSourceId")
        currency = self._required_text(base_currency, "BaseCurrency").upper()
        if len(currency) != 3 or not currency.isalpha():
            _fail("INVALID_PORTFOLIO_VALUE", "BaseCurrency must be a three-letter code")
        classification = self._required_text(
            evidence_classification, "EvidenceClassification"
        ).upper()
        if classification not in ALLOWED_EVIDENCE_CLASSIFICATIONS:
            _fail("SNAPSHOT_METADATA_INVALID", "invalid EvidenceClassification")

        candidate_file, candidates, candidate_hash = self._read_csv(
            candidate_path, "candidate artifact", CANDIDATE_REQUIRED_COLUMNS
        )
        if not candidates:
            _fail("CANDIDATE_METADATA_MISSING", "candidate artifact has no provenance rows")
        candidate_run = self._single(candidates, "RunId", "candidate artifact")
        candidate_date = self._iso_date(
            self._single(candidates, "AsOfDate", "candidate artifact"), "candidate AsOfDate"
        )
        score_version = self._single(candidates, "ScoreModelVersion", "candidate artifact")
        if candidate_run != run_id:
            _fail("RUN_ID_MISMATCH", "RunId conflicts with candidate artifact")
        if candidate_date != as_of_date:
            _fail("AS_OF_DATE_MISMATCH", "AsOfDate conflicts with candidate artifact")
        tickers = [str(row.get("Ticker", "")).strip().upper() for row in candidates]
        if any(not ticker for ticker in tickers) or len(tickers) != len(set(tickers)):
            _fail("CANDIDATE_ARTIFACT_INVALID", "candidate tickers are missing or duplicated")
        eligible_count = sum(
            self._boolean(row.get("PortfolioEligible"), "PortfolioEligible")
            for row in candidates
        )

        canonical_state = self._canonical_state(
            portfolio_state,
            portfolio_as_of_date=portfolio_as_of_date,
            portfolio_source_id=source_id,
            base_currency=currency,
        )
        state_hash = hashlib.sha256(self._canonical_bytes(canonical_state)).hexdigest()
        snapshot_id = (
            f"portfolio-snapshot-{portfolio_as_of_date.replace('-', '')}-{state_hash[:12]}"
        )

        risk_file, risk_rows, risk_hash = self._read_csv(
            risk_path, "risk artifact", RISK_REQUIRED_COLUMNS
        )
        risk_model_version = self._validate_risk_rows(
            risk_rows,
            run_id=run_id,
            as_of_date=as_of_date,
            score_model_version=score_version,
            portfolio_snapshot_id=snapshot_id,
            portfolio_as_of_date=portfolio_as_of_date,
        )
        if captured_timestamp is None:
            captured = datetime.now(timezone.utc).isoformat()
        else:
            try:
                timestamp = datetime.fromisoformat(captured_timestamp)
            except (TypeError, ValueError) as error:
                raise PortfolioSnapshotValidationError(
                    "SNAPSHOT_DATE_INVALID", "CapturedTimestamp is invalid"
                ) from error
            if timestamp.tzinfo is None:
                _fail("SNAPSHOT_DATE_INVALID", "CapturedTimestamp must include timezone")
            captured = timestamp.isoformat()

        if self._sha256(candidate_file) != candidate_hash or self._sha256(risk_file) != risk_hash:
            _fail("ARTIFACT_CHANGED", "bound artifact changed during snapshot construction")
        return {
            "PortfolioSnapshotContractVersion": SNAPSHOT_CONTRACT_VERSION,
            "BuilderVersion": BUILDER_VERSION,
            "PortfolioSnapshotId": snapshot_id,
            "PortfolioStateHash": state_hash,
            "RunId": run_id,
            "AsOfDate": as_of_date,
            "ScoreModelVersion": score_version,
            "RiskModelVersion": risk_model_version,
            "CandidateArtifactHash": candidate_hash,
            "RiskArtifactHash": risk_hash,
            "CandidateRowCount": len(candidates),
            "PortfolioEligibleCount": eligible_count,
            "PortfolioAsOfDate": portfolio_as_of_date,
            "PortfolioSourceId": source_id,
            "BaseCurrency": currency,
            "EvidenceClassification": classification,
            "CapturedTimestamp": captured,
            "RepositoryCommit": self._repository_commit(),
            "State": canonical_state,
            "ValidationStatus": "PASS",
            "PermittedAction": "NO_ACTION",
        }

    @classmethod
    def serialize_snapshot(cls, snapshot: Mapping[str, Any]) -> bytes:
        """Serialize a snapshot deterministically for immutable publication."""
        if not isinstance(snapshot, Mapping):
            _fail("SNAPSHOT_METADATA_INVALID", "snapshot must be an object")
        return (
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")

    @classmethod
    def publish_snapshot(cls, snapshot: Mapping[str, Any], output_path: Any) -> Path:
        """Atomically publish one snapshot without overwrite or repair."""
        path = Path(output_path)
        if path.exists():
            raise PortfolioSnapshotCollisionError(f"snapshot already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = cls.serialize_snapshot(snapshot)
        temporary: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(prefix=".tmp_snapshot_", dir=path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise PortfolioSnapshotCollisionError(
                    f"snapshot already exists: {path}"
                ) from error
            return path
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
