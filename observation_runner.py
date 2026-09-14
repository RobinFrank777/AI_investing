"""Dry-run authority mapper for the Observation Workbook.

Phase 1 only:
- reads current production artifacts
- validates run identity consistency
- prints the Daily_Run mapping
- NEVER writes the Observation Workbook
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from config import PROJECT_VERSION, REPO_ROOT
from current_run_status import load_current_run_status


RESULTS_DIR = REPO_ROOT / "results"
CANDIDATES_PATH = RESULTS_DIR / "production_candidates.csv"
ACTION_REPORT_PATH = RESULTS_DIR / "portfolio_action_report.txt"


def parse_colon_report(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in values:
            values[key] = value
    return values


def require_report_value(report: dict[str, str], key: str) -> str:
    value = str(report.get(key, "")).strip()
    if not value:
        raise RuntimeError(f"Missing required action-report field: {key}")
    return value


def require_unique(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        raise RuntimeError(f"production_candidates.csv missing column: {column}")

    values = frame[column].dropna().astype(str).str.strip()
    values = [value for value in values.unique() if value]

    if len(values) != 1:
        raise RuntimeError(
            f"Expected exactly one {column} in production_candidates.csv; "
            f"found {values}"
        )
    return values[0]


def parse_int(value: str, field_name: str) -> int:
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise RuntimeError(
            f"Expected integer for {field_name}; got {value!r}"
        ) from exc


def build_daily_run_preview() -> dict[str, object]:
    status = load_current_run_status()
    if not status:
        raise RuntimeError("current_run_status.json is missing or invalid")

    if status.get("OverallRunStatus") != "PASS":
        raise RuntimeError(
            "Latest production pipeline is not PASS; refusing Daily_Run mapping"
        )

    passed_steps = status.get("PassedSteps")
    total_steps = status.get("TotalSteps")
    if not isinstance(passed_steps, int) or not isinstance(total_steps, int):
        raise RuntimeError(
            "PassedSteps / TotalSteps are missing from current_run_status.json"
        )
    if total_steps <= 0 or passed_steps < 0:
        raise RuntimeError(
            f"Invalid pipeline step counts: {passed_steps}/{total_steps}"
        )

    if passed_steps != total_steps:
        raise RuntimeError(
            f"Pipeline is not complete: {passed_steps}/{total_steps} PASS"
        )

    frame = pd.read_csv(CANDIDATES_PATH)
    if frame.empty:
        raise RuntimeError("production_candidates.csv is empty")

    candidate_run_id = require_unique(frame, "RunId")
    candidate_as_of = require_unique(frame, "AsOfDate")
    universe_version = require_unique(frame, "UniverseVersion")
    score_model_version = require_unique(frame, "ScoreModelVersion")

    status_run_id = str(status.get("CurrentRunId", "")).strip()
    status_as_of = str(status.get("AsOfDate", "")).strip()

    if status_run_id != candidate_run_id:
        raise RuntimeError(
            f"RunId mismatch: status={status_run_id!r}, "
            f"candidates={candidate_run_id!r}"
        )
    if status_as_of != candidate_as_of:
        raise RuntimeError(
            f"AsOfDate mismatch: status={status_as_of!r}, "
            f"candidates={candidate_as_of!r}"
        )

    report = parse_colon_report(ACTION_REPORT_PATH)

    report_run_id = require_report_value(report, "RunId")
    report_as_of = require_report_value(report, "AsOfDate")
    report_universe = require_report_value(report, "UniverseVersion")
    report_score_model = require_report_value(report, "ScoreModelVersion")

    identity_checks = {
        "RunId": (candidate_run_id, report_run_id),
        "AsOfDate": (candidate_as_of, report_as_of),
        "UniverseVersion": (universe_version, report_universe),
        "ScoreModelVersion": (score_model_version, report_score_model),
    }
    for field_name, (left, right) in identity_checks.items():
        if left != right:
            raise RuntimeError(
                f"{field_name} mismatch: candidates={left!r}, "
                f"action_report={right!r}"
            )

    if "TradeSignal" not in frame.columns:
        raise RuntimeError(
            "production_candidates.csv missing column: TradeSignal"
        )

    signal_counts = (
        frame["TradeSignal"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .value_counts()
    )
    buy = int(signal_counts.get("BUY", 0))
    watch = int(signal_counts.get("WATCH", 0))
    ignore = int(signal_counts.get("IGNORE", 0))

    configured = parse_int(
        require_report_value(report, "Configured Universe"),
        "Configured Universe",
    )
    ready = parse_int(
        require_report_value(report, "Research Ready"),
        "Research Ready",
    )
    excluded = parse_int(
        require_report_value(report, "Excluded"),
        "Excluded",
    )
    provider_rejected = parse_int(
        require_report_value(report, "Provider Rejected"),
        "Provider Rejected",
    )
    stale_market_data = parse_int(
        require_report_value(report, "Stale Market Data"),
        "Stale Market Data",
    )
    insufficient_history = parse_int(
        require_report_value(report, "Insufficient History"),
        "Insufficient History",
    )

    if ready + excluded != configured:
        raise RuntimeError(
            f"Coverage arithmetic mismatch: {ready} + {excluded} != {configured}"
        )

    if buy + watch + ignore != ready:
        raise RuntimeError(
            "Signal arithmetic mismatch: "
            f"{buy} + {watch} + {ignore} != {ready}"
        )

    final_status = require_report_value(report, "Portfolio Decision")
    report_status = require_report_value(report, "Report Status")
    if final_status != report_status:
        raise RuntimeError(
            f"Action report status mismatch: "
            f"Portfolio Decision={final_status!r}, Report Status={report_status!r}"
        )

    return {
        "Date": date.fromisoformat(candidate_as_of),
        "Version": PROJECT_VERSION,
        "PipelineStatus": status["OverallRunStatus"],
        "PassSteps": f"{passed_steps}/{total_steps}",
        "RunId": candidate_run_id,
        "AsOfDate": date.fromisoformat(candidate_as_of),
        "UniverseVersion": universe_version,
        "ScoreModelVersion": score_model_version,
        "RiskModelVersion": require_report_value(report, "RiskModelVersion"),
        "UniverseConfigured": configured,
        "Ready": ready,
        "Excluded": excluded,
        "ProviderRejected": provider_rejected,
        "StaleMarketData": stale_market_data,
        "InsufficientHistory": insufficient_history,
        "ExcludedSymbols": require_report_value(report, "Excluded Symbols"),
        "CoverageStatus": require_report_value(report, "Data Coverage"),
        "BUY": buy,
        "WATCH": watch,
        "IGNORE": ignore,
        "FinalStatus": final_status,
        "Notes": (
            "DRY_RUN authority mapping only; "
            "current_run_status.json + production_candidates.csv + "
            "portfolio_action_report.txt"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Observation Workbook authority mapper (dry-run only)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate production authorities and print Daily_Run mapping",
    )
    args = parser.parse_args()

    if not args.dry_run:
        parser.error("Phase 1 supports --dry-run only; workbook writes are disabled")

    preview = build_daily_run_preview()

    print("\nOBSERVATION RUNNER — DAILY_RUN DRY RUN")
    print("=" * 72)
    for key, value in preview.items():
        print(f"{key:<20}: {value}")
    print("=" * 72)
    print("PASS: authority checks completed")
    print("NO WORKBOOK WRITE WAS PERFORMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
