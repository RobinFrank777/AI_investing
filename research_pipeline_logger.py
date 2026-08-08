"""JSON logging for daily research pipeline status records."""

import json
from datetime import date
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
REQUIRED_STATUS_COLUMNS = ("StepName", "Status", "Message")
ALLOWED_STATUSES = frozenset({"PASS", "FAILED", "SKIPPED"})


def _normalized_date(value):
    if value is None:
        return date.today().isoformat()
    try:
        return pd.to_datetime(value, errors="raise").date().isoformat()
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("run_date must be a valid date") from error


def pipeline_log_path(run_date=None, log_dir=None):
    """Return the deterministic daily JSON log path."""
    normalized = _normalized_date(run_date)
    directory = DEFAULT_LOG_DIR if log_dir is None else Path(log_dir)
    return directory / f"daily_research_pipeline_{normalized.replace('-', '')}.json"


def _pipeline_status(summary):
    if sum(summary.values()) == 0:
        return "EMPTY"
    if summary["FAILED"] == 0 and summary["SKIPPED"] == 0:
        return "PASS"
    if summary["PASS"] == 0 and summary["FAILED"] > 0:
        return "FAILED"
    return "PARTIAL"


def build_pipeline_log(status, run_date=None):
    """Build the fixed JSON-serializable pipeline log structure."""
    if status is None:
        status = pd.DataFrame(columns=REQUIRED_STATUS_COLUMNS)
    if not isinstance(status, pd.DataFrame):
        raise TypeError("pipeline status must be a pandas DataFrame or None")
    missing = [column for column in REQUIRED_STATUS_COLUMNS if column not in status]
    if missing:
        raise ValueError(
            "pipeline status is missing required columns: " + ", ".join(missing)
        )

    inferred_date = run_date
    if inferred_date is None and "RunDate" in status and not status.empty:
        inferred_date = status["RunDate"].iloc[0]
    normalized_date = _normalized_date(inferred_date)
    summary = {key: 0 for key in ("PASS", "FAILED", "SKIPPED")}
    steps = []
    for _, row in status.iterrows():
        step_status = str(row["Status"]).strip().upper()
        if step_status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid pipeline step status: {step_status}")
        summary[step_status] += 1
        message = "" if pd.isna(row["Message"]) else str(row["Message"])
        steps.append(
            {
                "name": "" if pd.isna(row["StepName"]) else str(row["StepName"]),
                "status": step_status,
                "error": "" if step_status == "PASS" else message,
            }
        )
    return {
        "run_date": normalized_date,
        "pipeline_status": _pipeline_status(summary),
        "steps": steps,
        "summary": summary,
    }


def save_pipeline_log(status, run_date=None, log_dir=None):
    """Save a daily pipeline log as formatted JSON and return its path."""
    payload = build_pipeline_log(status, run_date=run_date)
    path = pipeline_log_path(payload["run_date"], log_dir=log_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path
