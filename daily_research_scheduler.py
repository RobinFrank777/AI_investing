"""Stable automation entry point for the daily research pipeline."""

from datetime import date, datetime

import daily_research_pipeline
import research_pipeline_logger


def _run_date(value):
    if value is None:
        return date.today().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()


def _empty_summary():
    return {"PASS": 0, "FAILED": 0, "SKIPPED": 0}


def _result(run_date, pipeline_status, log_path, summary):
    return {
        "RunDate": run_date,
        "PipelineStatus": pipeline_status,
        "LogPath": str(log_path),
        "Summary": summary,
    }


def run_scheduled_research(run_date=None):
    """Invoke the daily pipeline and return a compact automation result."""
    try:
        normalized_date = _run_date(run_date)
    except (TypeError, ValueError):
        normalized_date = date.today().isoformat()
        log_path = research_pipeline_logger.pipeline_log_path(normalized_date)
        return _result(normalized_date, "FAILED", log_path, _empty_summary())

    try:
        pipeline_result = daily_research_pipeline.run_daily_research_pipeline(
            run_date=normalized_date
        )
        statuses = [
            str(value).strip().upper()
            for value in pipeline_result["status"]["Status"]
        ]
        summary = _empty_summary()
        for status in statuses:
            if status in summary:
                summary[status] += 1
        completed = summary["FAILED"] == 0 and summary["SKIPPED"] == 0
        pipeline_status = "PASS" if completed else "FAILED"
    except Exception:
        summary = _empty_summary()
        pipeline_status = "FAILED"

    try:
        log_path = research_pipeline_logger.pipeline_log_path(normalized_date)
    except Exception:
        log_path = ""
    return _result(normalized_date, pipeline_status, log_path, summary)
