"""Truthful, fail-closed metadata checks for current production reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from config import PRIMARY_UNIVERSE_VERSION
from current_run_status import load_current_run_status
from production_candidate_builder import MAX_STALENESS_DAYS
from universe_metadata import MATCH, MISMATCH, dataframe_universe_compatibility


PASS = "PASS"
FAILED = "FAILED"
INCOMPATIBLE = "INCOMPATIBLE"
STALE = "STALE"
UNKNOWN = "UNKNOWN"
NO_ACTION = "NO_ACTION"
RESEARCH_ONLY = "RESEARCH_ONLY"

STATUS_PRECEDENCE = (FAILED, INCOMPATIBLE, STALE, UNKNOWN, NO_ACTION, PASS)
METADATA_FIELDS = (
    "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
    "RiskModelVersion",
)

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
PRODUCTION_ARTIFACT_PATHS = {
    "Production Candidate": RESULTS_DIR / "production_candidates.csv",
    "Portfolio Risk": RESULTS_DIR / "portfolio_risk_inputs.csv",
    "Model Portfolio": RESULTS_DIR / "model_portfolio.csv",
    "Position Sizing": RESULTS_DIR / "model_portfolio_sizing.csv",
    "Order Draft": RESULTS_DIR / "order_draft.csv",
    "Order Review": RESULTS_DIR / "order_review.csv",
}
ACTION_ARTIFACTS = tuple(PRODUCTION_ARTIFACT_PATHS)[1:]
REQUIRED_SCHEMA = {
    "Production Candidate": {
        "Ticker", "Eligibility", "TradeSignal",
    },
    "Portfolio Risk": {
        "Ticker", "RiskValidationStatus",
    },
    "Model Portfolio": {
        "Ticker", "PortfolioStatus",
    },
    "Position Sizing": {
        "Ticker", "TargetShares",
    },
    "Order Draft": {
        "Ticker", "OrderStatus",
    },
    "Order Review": {
        "Ticker", "ReviewStatus", "PortfolioReviewFlag",
    },
}


@dataclass(frozen=True)
class ReportAssessment:
    status: str
    metadata: dict[str, str]
    artifact_statuses: dict[str, str]
    reasons: tuple[str, ...]
    action_required: bool


def _single_text(frame, field):
    if field not in frame.columns or frame.empty:
        return None, UNKNOWN
    values = frame[field].fillna("").astype(str).str.strip()
    if (values == "").any():
        return None, UNKNOWN
    unique = values.unique().tolist()
    if len(unique) != 1:
        return None, INCOMPATIBLE
    return unique[0], PASS


def _candidate_requires_action(candidate):
    if candidate.empty:
        return False
    if "Eligibility" in candidate and "TradeSignal" in candidate:
        eligibility = candidate["Eligibility"].fillna("").astype(str).str.upper()
        signals = candidate["TradeSignal"].fillna("").astype(str).str.upper()
        return bool(((eligibility == "ELIGIBLE") & (signals == "BUY")).any())
    return True


def _has_explicit_failure(name, frame):
    checks = {
        "Portfolio Risk": ("RiskValidationStatus", {"FAILED"}),
        "Order Review": ("ReviewStatus", {"BLOCKED"}),
    }
    column, failed_values = checks.get(name, (None, set()))
    if column not in frame.columns:
        return False
    values = set(frame[column].fillna("").astype(str).str.strip().str.upper())
    return bool(values & failed_values)


def _aggregate(states):
    for status in STATUS_PRECEDENCE:
        if status in states:
            return status
    return UNKNOWN


def evaluate_report_artifacts(artifacts, *, report_date=None):
    """Evaluate current-run evidence without repairing or inferring metadata."""
    candidate = artifacts.get("Production Candidate")
    if candidate is None:
        return ReportAssessment(
            UNKNOWN, {field: "MISSING" for field in METADATA_FIELDS},
            {"Production Candidate": UNKNOWN},
            ("Production Candidate is missing",), False,
        )
    if not isinstance(candidate, pd.DataFrame):
        raise TypeError("report artifacts must be pandas DataFrames or None")

    candidate_missing = sorted(REQUIRED_SCHEMA["Production Candidate"] - set(candidate.columns))
    if candidate_missing:
        return ReportAssessment(
            FAILED, {field: "MISSING" for field in METADATA_FIELDS},
            {"Production Candidate": FAILED},
            ("Production Candidate schema missing: " + ", ".join(candidate_missing),),
            False,
        )

    action_required = _candidate_requires_action(candidate)
    required_names = ("Production Candidate",) + (ACTION_ARTIFACTS if action_required else ())
    states = []
    artifact_states = {}
    reasons = []
    values_by_field = {field: [] for field in METADATA_FIELDS}

    if candidate.empty:
        artifact_states["Production Candidate"] = NO_ACTION
        states.append(NO_ACTION)

    for name in required_names:
        frame = artifacts.get(name)
        if frame is None:
            artifact_states[name] = UNKNOWN
            states.append(UNKNOWN)
            reasons.append(f"{name} is missing")
            continue
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("report artifacts must be pandas DataFrames or None")
        missing_columns = sorted(REQUIRED_SCHEMA[name] - set(frame.columns))
        if missing_columns:
            artifact_states[name] = FAILED
            states.append(FAILED)
            reasons.append(f"{name} schema missing: " + ", ".join(missing_columns))
            continue
        if _has_explicit_failure(name, frame):
            artifact_states[name] = FAILED
            states.append(FAILED)
            reasons.append(f"{name} contains an explicit validation failure")
            continue

        if name == "Production Candidate" and frame.empty:
            continue

        local_states = []
        for field in METADATA_FIELDS:
            # Universe is authoritative at candidate creation; RiskModelVersion
            # starts at the risk stage. Every action-stage artifact must carry
            # both so reports can prove end-to-end identity.
            applicable = (
                field != "RiskModelVersion" or name != "Production Candidate"
            ) and (
                field != "UniverseVersion" or name != "Portfolio Risk"
            )
            if not applicable:
                continue
            value, state = _single_text(frame, field)
            local_states.append(state)
            if state == PASS:
                values_by_field[field].append(value)
            else:
                reasons.append(f"{name} {field} is missing, blank, or mixed")

        if name == "Production Candidate":
            universe_state = dataframe_universe_compatibility(frame)
            if universe_state == MISMATCH:
                local_states.append(INCOMPATIBLE)
                reasons.append("Production Candidate UniverseVersion mismatches current authority")
            elif universe_state != MATCH:
                local_states.append(UNKNOWN)

        artifact_state = _aggregate(local_states or [PASS])
        if artifact_states.get(name) != NO_ACTION:
            artifact_states[name] = artifact_state
        states.append(artifact_states[name])

    for field, values in values_by_field.items():
        if len(set(values)) > 1:
            states.append(STALE if field == "AsOfDate" else INCOMPATIBLE)
            reasons.append(f"required artifacts contain mismatched {field}")

    as_of_values = values_by_field["AsOfDate"]
    if as_of_values:
        try:
            as_of = pd.Timestamp(as_of_values[0]).date()
            reference = date.today() if report_date is None else pd.Timestamp(report_date).date()
            age = (reference - as_of).days
            if age < 0:
                states.append(INCOMPATIBLE)
                reasons.append("AsOfDate is in the future")
            elif age > MAX_STALENESS_DAYS:
                states.append(STALE)
                reasons.append(f"AsOfDate is stale by {age} days")
        except (TypeError, ValueError, OverflowError):
            states.append(UNKNOWN)
            reasons.append("AsOfDate cannot be verified")

    if not action_required and not candidate.empty:
        states.append(NO_ACTION)

    metadata = {}
    for field, values in values_by_field.items():
        unique = list(dict.fromkeys(values))
        metadata[field] = unique[0] if len(unique) == 1 else (
            "MISMATCH" if len(unique) > 1 else "MISSING"
        )
    metadata["UniverseVersionExpected"] = PRIMARY_UNIVERSE_VERSION
    return ReportAssessment(
        _aggregate(states or [PASS]), metadata, artifact_states,
        tuple(dict.fromkeys(reasons)), action_required,
    )


def load_current_report_artifacts(paths=None):
    """Read current paths only; never search archives or legacy backtests."""
    selected = PRODUCTION_ARTIFACT_PATHS if paths is None else paths
    loaded = {}
    for name, path_value in selected.items():
        path = Path(path_value)
        if not path.is_file():
            loaded[name] = None
            continue
        try:
            loaded[name] = pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError, OSError):
            loaded[name] = None
    return loaded


def assess_current_report(paths=None, *, report_date=None, run_status_path=None):
    context = (
        load_current_run_status()
        if run_status_path is None
        else load_current_run_status(run_status_path)
    )
    if context and context.get("OverallRunStatus") == FAILED:
        metadata = {field: "MISSING" for field in METADATA_FIELDS}
        metadata["RunId"] = context.get("CurrentRunId") or "MISSING"
        metadata["AsOfDate"] = context.get("AsOfDate") or "MISSING"
        metadata["UniverseVersionExpected"] = PRIMARY_UNIVERSE_VERSION
        stage = context.get("FailedStage") or "UNKNOWN"
        reason = context.get("FailureReason") or "Required pipeline stage failed"
        return ReportAssessment(
            FAILED, metadata, {},
            (f"Latest pipeline attempt failed at {stage}: {reason}",
             "Prior production artifacts are historical, not current"),
            False,
        )

    assessment = evaluate_report_artifacts(
        load_current_report_artifacts(paths), report_date=report_date
    )
    if context and context.get("OverallRunStatus") == PASS:
        current_id = str(context.get("CurrentRunId") or "").strip()
        artifact_id = assessment.metadata.get("RunId", "MISSING")
        if not current_id or artifact_id != current_id:
            return ReportAssessment(
                INCOMPATIBLE, assessment.metadata, assessment.artifact_statuses,
                tuple((*assessment.reasons,
                       "Latest successful pipeline RunId does not match report artifacts")),
                assessment.action_required,
            )
        current_as_of = str(context.get("AsOfDate") or "").strip()
        artifact_as_of = assessment.metadata.get("AsOfDate", "MISSING")
        if not current_as_of or artifact_as_of != current_as_of:
            return ReportAssessment(
                STALE, assessment.metadata, assessment.artifact_statuses,
                tuple((*assessment.reasons,
                       "Latest successful pipeline AsOfDate does not match report artifacts")),
                assessment.action_required,
            )
    return assessment
