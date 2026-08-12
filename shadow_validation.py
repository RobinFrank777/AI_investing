"""Non-production validation of candidate and point-in-time risk artifacts."""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CANDIDATE_PATH = PROJECT_ROOT / "results" / "validated_portfolio_candidates.csv"
DEFAULT_RISK_PATH = PROJECT_ROOT / "results" / "portfolio_risk_inputs.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "shadow_validation_report.csv"

JOIN_KEYS = ("Ticker", "RunId", "AsOfDate")
CANDIDATE_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "ScoreModelVersion", "CandidateRank",
    "FinalScore", "TradeSignal", "Eligibility", "PortfolioEligible",
    "ValidationStatus",
)
RISK_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "ScoreModelVersion", "RiskModelVersion",
    "RiskStatus", "RiskValidationStatus", "RiskValidationReason",
    "ObservationEndDate",
)
OUTPUT_COLUMNS = (
    "Ticker", "RunId", "AsOfDate", "ScoreModelVersion", "RiskModelVersion",
    "CandidateRank", "FinalScore", "TradeSignal", "PortfolioEligible",
    "RiskStatus", "RiskValidationStatus", "ShadowStatus", "ShadowReason",
)
METRIC_COLUMNS = (
    "TotalCandidateRows", "PortfolioEligibleRows", "RiskRows",
    "MatchedEligibleRows", "MissingRiskRows", "ShadowReadyRows",
    "ShadowPendingRows", "ShadowBlockedRows", "MetadataMismatchRows",
    "OrphanRiskRows",
    "ExactMatchCoveragePercent", "ShadowReadyCoveragePercent",
)
FORBIDDEN_OUTPUT_COLUMNS = (
    "BacktestScore", "SharpeRatio", "MaxDrawdown", "RiskLevel",
    "TargetShares", "OrderValue", "OrderAction",
)


def empty_shadow_report():
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _read_csv(path, label):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"{label} file is empty: {path}") from error


def _normalize_identity(frame, label):
    result = frame.copy(deep=True)
    for column in JOIN_KEYS:
        result[column] = result[column].fillna("").astype(str).str.strip()
        if (result[column] == "").any():
            raise ValueError(f"{label} contains missing {column}")
    result["Ticker"] = result.Ticker.str.upper()
    try:
        result["AsOfDate"] = pd.to_datetime(
            result.AsOfDate, errors="raise"
        ).dt.date.astype(str)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label} contains invalid AsOfDate") from error
    duplicates = result.duplicated(list(JOIN_KEYS), keep=False)
    if duplicates.any():
        duplicate_keys = (
            result.loc[duplicates, list(JOIN_KEYS)].astype(str)
            .agg("/".join, axis=1).sort_values().unique().tolist()
        )
        code = "DUPLICATE_CANDIDATE" if label == "candidate input" else "DUPLICATE_RISK_ROW"
        raise ValueError(f"{code}: " + ", ".join(duplicate_keys))
    return result


def _validate_candidates(candidates):
    if not isinstance(candidates, pd.DataFrame):
        raise TypeError("candidates must be a pandas DataFrame")
    missing = [column for column in CANDIDATE_COLUMNS if column not in candidates]
    if missing:
        raise ValueError("candidate input missing columns: " + ", ".join(missing))
    if candidates.empty:
        return candidates.copy(deep=True)
    frame = _normalize_identity(candidates, "candidate input")
    for column in ("ScoreModelVersion", "TradeSignal", "Eligibility", "ValidationStatus"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise ValueError(f"candidate input contains missing {column}")
    for column in ("CandidateRank", "FinalScore"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any() or not np.isfinite(frame[column]).all():
            raise ValueError(f"candidate input contains non-finite {column}")
    eligible = frame.PortfolioEligible
    if eligible.dtype != bool:
        eligible = eligible.astype(str).str.strip().str.upper().map(
            {"TRUE": True, "FALSE": False}
        )
    if eligible.isna().any():
        raise ValueError("candidate input contains invalid PortfolioEligible")
    frame["PortfolioEligible"] = eligible.astype(bool)
    return frame


def _validate_risk(risk):
    if not isinstance(risk, pd.DataFrame):
        raise TypeError("risk_inputs must be a pandas DataFrame")
    missing = [column for column in RISK_COLUMNS if column not in risk]
    if missing:
        raise ValueError("risk input missing columns: " + ", ".join(missing))
    if risk.empty:
        return risk.copy(deep=True)
    frame = _normalize_identity(risk, "risk input")
    for column in (
        "ScoreModelVersion", "RiskModelVersion", "RiskStatus",
        "RiskValidationStatus",
    ):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise ValueError(f"risk input contains missing {column}")
    frame["RiskStatus"] = frame.RiskStatus.str.upper()
    frame["RiskValidationStatus"] = frame.RiskValidationStatus.str.upper()
    frame["RiskValidationReason"] = frame.RiskValidationReason.fillna("").astype(str).str.strip()
    return frame


def _mismatch_reason(candidate, risk):
    same_ticker = risk.loc[risk.Ticker == candidate.Ticker]
    if same_ticker.empty:
        return None
    same_date = same_ticker.loc[same_ticker.AsOfDate == candidate.AsOfDate]
    if not same_date.empty and (same_date.RunId != candidate.RunId).any():
        return "RUN_ID_MISMATCH"
    same_run = same_ticker.loc[same_ticker.RunId == candidate.RunId]
    if not same_run.empty and (same_run.AsOfDate != candidate.AsOfDate).any():
        return "AS_OF_DATE_MISMATCH"
    return None


def _classify(candidate, risk_row):
    if candidate.ScoreModelVersion != risk_row.ScoreModelVersion:
        return "SHADOW_METADATA_MISMATCH", "SCORE_MODEL_VERSION_MISMATCH"
    if risk_row.RiskStatus == "READY" and risk_row.RiskValidationStatus == "PASS":
        try:
            observation_end = pd.Timestamp(risk_row.ObservationEndDate)
            as_of_date = pd.Timestamp(candidate.AsOfDate)
        except (TypeError, ValueError) as error:
            return "SHADOW_BLOCKED", f"INVALID_OBSERVATION_END_DATE: {error}"
        if pd.isna(observation_end) or observation_end > as_of_date:
            return "SHADOW_BLOCKED", "FUTURE_OBSERVATION_DATE"
        return "SHADOW_READY", "SHADOW_CONTRACT_COMPLETE"
    if risk_row.RiskStatus == "PENDING":
        detail = risk_row.RiskValidationReason or "MISSING_FAILURE_REASON"
        return "SHADOW_PENDING", f"RISK_PENDING: {detail}"
    if risk_row.RiskStatus == "BLOCKED":
        detail = risk_row.RiskValidationReason or "MISSING_FAILURE_REASON"
        return "SHADOW_BLOCKED", f"RISK_BLOCKED: {detail}"
    if risk_row.RiskValidationStatus != "PASS":
        detail = risk_row.RiskValidationReason or "MISSING_FAILURE_REASON"
        return "SHADOW_BLOCKED", f"RISK_VALIDATION_FAILED: {detail}"
    return "SHADOW_BLOCKED", "INVALID_RISK_STATUS_COMBINATION"


def _coverage(candidates, risk, report):
    eligible_rows = int(candidates.PortfolioEligible.sum()) if not candidates.empty else 0
    matched = int(report.RiskStatus.notna().sum()) if not report.empty else 0
    missing = int((report.ShadowStatus == "SHADOW_MISSING_RISK").sum()) if not report.empty else 0
    ready = int((report.ShadowStatus == "SHADOW_READY").sum()) if not report.empty else 0
    pending = int((report.ShadowStatus == "SHADOW_PENDING").sum()) if not report.empty else 0
    blocked = int((report.ShadowStatus == "SHADOW_BLOCKED").sum()) if not report.empty else 0
    mismatch = int((report.ShadowStatus == "SHADOW_METADATA_MISMATCH").sum()) if not report.empty else 0
    eligible_keys = set(
        candidates.loc[candidates.PortfolioEligible, list(JOIN_KEYS)]
        .itertuples(index=False, name=None)
    ) if not candidates.empty else set()
    risk_keys = set(risk.loc[:, list(JOIN_KEYS)].itertuples(index=False, name=None)) if not risk.empty else set()
    orphan_count = len(risk_keys - eligible_keys)
    denominator = eligible_rows or None
    values = {
        "TotalCandidateRows": len(candidates),
        "PortfolioEligibleRows": eligible_rows,
        "RiskRows": len(risk),
        "MatchedEligibleRows": matched,
        "MissingRiskRows": missing,
        "ShadowReadyRows": ready,
        "ShadowPendingRows": pending,
        "ShadowBlockedRows": blocked,
        "MetadataMismatchRows": mismatch,
        "OrphanRiskRows": orphan_count,
        "ExactMatchCoveragePercent": (matched / denominator * 100) if denominator else None,
        "ShadowReadyCoveragePercent": (ready / denominator * 100) if denominator else None,
    }
    metrics = {column: values[column] for column in METRIC_COLUMNS}
    failure_rows = report.loc[report.ShadowStatus != "SHADOW_READY", "ShadowReason"]
    reasons = failure_rows.dropna().value_counts().sort_index().to_dict()
    if eligible_rows == 0:
        reasons["NO_PORTFOLIO_ELIGIBLE_CANDIDATE"] = 1
    if orphan_count:
        reasons["RISK_ROW_ORPHAN"] = orphan_count
    metrics["FailureReasons"] = reasons
    risk_distribution = (
        risk.groupby(["RiskStatus", "RiskValidationStatus"], dropna=False)
        .size().sort_index()
    ) if not risk.empty else pd.Series(dtype="int64")
    metrics["RiskStatusDistribution"] = {
        f"{status}/{validation}": int(count)
        for (status, validation), count in risk_distribution.items()
    }
    return metrics


def validate_shadow(candidates, risk_inputs):
    """Return a shadow-only row report and coverage metrics without mutation."""
    candidate_source = _validate_candidates(candidates)
    risk_source = _validate_risk(risk_inputs)
    eligible = candidate_source.loc[candidate_source.PortfolioEligible].copy()
    if eligible.empty:
        return empty_shadow_report(), _coverage(candidate_source, risk_source, empty_shadow_report())

    risk_lookup = risk_source.set_index(list(JOIN_KEYS), drop=False)
    rows = []
    for _, candidate in eligible.iterrows():
        key = tuple(candidate[column] for column in JOIN_KEYS)
        base = {
            "Ticker": candidate.Ticker,
            "RunId": candidate.RunId,
            "AsOfDate": candidate.AsOfDate,
            "ScoreModelVersion": candidate.ScoreModelVersion,
            "CandidateRank": candidate.CandidateRank,
            "FinalScore": candidate.FinalScore,
            "TradeSignal": candidate.TradeSignal,
            "PortfolioEligible": candidate.PortfolioEligible,
        }
        if key not in risk_lookup.index:
            mismatch = _mismatch_reason(candidate, risk_source)
            status = "SHADOW_METADATA_MISMATCH" if mismatch else "SHADOW_MISSING_RISK"
            rows.append({
                **base, "ShadowStatus": status,
                "ShadowReason": mismatch or "RISK_ROW_MISSING",
            })
            continue
        risk_row = risk_lookup.loc[key]
        shadow_status, shadow_reason = _classify(candidate, risk_row)
        rows.append({
            **base,
            "RiskModelVersion": risk_row.RiskModelVersion,
            "RiskStatus": risk_row.RiskStatus,
            "RiskValidationStatus": risk_row.RiskValidationStatus,
            "ShadowStatus": shadow_status,
            "ShadowReason": shadow_reason,
        })
    report = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values(
        ["AsOfDate", "RunId", "CandidateRank", "Ticker"], kind="mergesort"
    ).reset_index(drop=True)
    return report, _coverage(candidate_source, risk_source, report)


def save_shadow_report(report, output_path=DEFAULT_OUTPUT_PATH):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return path


def run_shadow_validation(
    candidate_path=DEFAULT_CANDIDATE_PATH,
    risk_path=DEFAULT_RISK_PATH,
    output_path=DEFAULT_OUTPUT_PATH,
):
    candidates = _read_csv(candidate_path, "candidate input")
    risk = _read_csv(risk_path, "risk input")
    report, metrics = validate_shadow(candidates, risk)
    saved = save_shadow_report(report, output_path)
    return report, metrics, saved


if __name__ == "__main__":
    shadow, coverage, saved_path = run_shadow_validation()
    for name in METRIC_COLUMNS:
        print(f"{name}: {coverage[name]}")
    print(f"Output: {saved_path}")
