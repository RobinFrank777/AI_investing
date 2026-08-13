"""Lightweight authority record for the latest production pipeline attempt."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from config import RESULTS_DIR_PATH
from market_session import latest_completed_session_date


CURRENT_RUN_STATUS_PATH = RESULTS_DIR_PATH / "current_run_status.json"


def _timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_attempt_id():
    return "pipeline-" + uuid.uuid4().hex[:16]


def write_current_run_status(values, path=CURRENT_RUN_STATUS_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(values)
    payload["UpdatedAt"] = _timestamp()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return payload


def start_current_run(path=CURRENT_RUN_STATUS_PATH):
    started = _timestamp()
    return write_current_run_status(
        {
            "CurrentRunId": new_attempt_id(),
            "StartTime": started,
            "AsOfDate": latest_completed_session_date().isoformat(),
            "OverallRunStatus": "RUNNING",
            "FailedStage": "",
            "FailureReason": "",
        },
        path,
    )


def finish_current_run(context, *, status, failed_stage="", reason="",
                       current_run_id=None, as_of_date=None,
                       path=CURRENT_RUN_STATUS_PATH):
    result = dict(context)
    result.update(
        {
            "CurrentRunId": current_run_id or context["CurrentRunId"],
            "AsOfDate": as_of_date or context.get("AsOfDate", ""),
            "OverallRunStatus": status,
            "FailedStage": failed_stage,
            "FailureReason": reason,
        }
    )
    return write_current_run_status(result, path)


def load_current_run_status(path=CURRENT_RUN_STATUS_PATH):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
