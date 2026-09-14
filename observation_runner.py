"""Dry-run authority mapper for the Observation Workbook.

Phase 2:
- reads current production artifacts
- validates run identity consistency
- prints the Daily_Run mapping
- prints Candidate_Tracking mappings for BUY/WATCH candidates
- NEVER writes the Observation Workbook
"""

from __future__ import annotations

import argparse
import math
from datetime import date
from pathlib import Path

import pandas as pd

from config import PROJECT_VERSION, REPO_ROOT
from current_run_status import load_current_run_status


RESULTS_DIR = REPO_ROOT / "results"
CANDIDATES_PATH = RESULTS_DIR / "production_candidates.csv"
ACTION_REPORT_PATH = RESULTS_DIR / "portfolio_action_report.txt"
STOCK_RANK_PATH = RESULTS_DIR / "stock_rank.csv"
COMBINED_SCORE_PATH = RESULTS_DIR / "combined_score.csv"

TRACKED_SIGNALS = {"BUY", "WATCH"}


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


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise RuntimeError(
            f"{label} missing required columns: {', '.join(missing)}"
        )


def _optional_combined_values(
    ticker: str,
    *,
    run_id: str,
    as_of_date: str,
    universe_version: str,
    score_model_version: str,
) -> tuple[object, object]:
    if not COMBINED_SCORE_PATH.is_file():
        return None, None

    frame = pd.read_csv(COMBINED_SCORE_PATH)
    if frame.empty:
        return None, None

    _require_columns(
        frame,
        (
            "Ticker",
            "RunId",
            "AsOfDate",
            "UniverseVersion",
            "ScoreModelVersion",
            "FundamentalScore",
            "CombinedScore",
        ),
        "combined_score.csv",
    )

    matches = frame.loc[
        frame["Ticker"].astype(str).str.strip().str.upper().eq(ticker)
    ].copy()

    if matches.empty:
        return None, None
    if len(matches) != 1:
        raise RuntimeError(
            f"combined_score.csv expected one row for {ticker}; found {len(matches)}"
        )

    row = matches.iloc[0]
    checks = {
        "RunId": run_id,
        "AsOfDate": as_of_date,
        "UniverseVersion": universe_version,
        "ScoreModelVersion": score_model_version,
    }
    for field_name, expected in checks.items():
        actual = str(row[field_name]).strip()
        if actual != expected:
            raise RuntimeError(
                f"combined_score.csv {ticker} {field_name} mismatch: "
                f"{actual!r} != {expected!r}"
            )

    fundamental = row["FundamentalScore"]
    combined = row["CombinedScore"]
    fundamental = None if pd.isna(fundamental) else float(fundamental)
    combined = None if pd.isna(combined) else float(combined)
    return fundamental, combined


def build_candidate_tracking_previews() -> list[dict[str, object]]:
    candidates = pd.read_csv(CANDIDATES_PATH)
    if candidates.empty:
        raise RuntimeError("production_candidates.csv is empty")

    _require_columns(
        candidates,
        (
            "Ticker",
            "RunId",
            "AsOfDate",
            "CandidateRank",
            "FinalScore",
            "TradeSignal",
            "ScoreModelVersion",
            "UniverseVersion",
        ),
        "production_candidates.csv",
    )

    run_id = require_unique(candidates, "RunId")
    as_of_date = require_unique(candidates, "AsOfDate")
    universe_version = require_unique(candidates, "UniverseVersion")
    score_model_version = require_unique(candidates, "ScoreModelVersion")

    signals = candidates["TradeSignal"].fillna("").astype(str).str.strip().str.upper()
    tracked = candidates.loc[signals.isin(TRACKED_SIGNALS)].copy()
    tracked["_Signal"] = signals.loc[tracked.index]

    if tracked.empty:
        return []

    stock_rank = pd.read_csv(STOCK_RANK_PATH)
    if stock_rank.empty:
        raise RuntimeError("stock_rank.csv is empty")

    _require_columns(
        stock_rank,
        (
            "Ticker",
            "MarketDataDate",
            "Close",
            "FinalScore",
            "TradeSignal",
            "Reason",
            "ScoreModelVersion",
            "UniverseVersion",
        ),
        "stock_rank.csv",
    )

    previews: list[dict[str, object]] = []

    for _, candidate in tracked.sort_values(
        ["CandidateRank", "Ticker"], kind="mergesort"
    ).iterrows():
        ticker = str(candidate["Ticker"]).strip().upper()
        signal = str(candidate["_Signal"]).strip().upper()

        rank_value = candidate["CandidateRank"]
        if pd.isna(rank_value):
            raise RuntimeError(f"{ticker} CandidateRank is missing")
        rank = int(rank_value)
        if float(rank_value) != rank or rank < 1:
            raise RuntimeError(f"{ticker} CandidateRank is invalid: {rank_value!r}")

        final_score = float(candidate["FinalScore"])
        if not math.isfinite(final_score):
            raise RuntimeError(f"{ticker} FinalScore is not finite")

        matches = stock_rank.loc[
            stock_rank["Ticker"].astype(str).str.strip().str.upper().eq(ticker)
        ].copy()
        if len(matches) != 1:
            raise RuntimeError(
                f"stock_rank.csv expected exactly one row for {ticker}; "
                f"found {len(matches)}"
            )

        rank_row = matches.iloc[0]
        checks = {
            "MarketDataDate": as_of_date,
            "ScoreModelVersion": score_model_version,
            "UniverseVersion": universe_version,
            "TradeSignal": signal,
        }
        for field_name, expected in checks.items():
            actual = str(rank_row[field_name]).strip()
            if field_name == "TradeSignal":
                actual = actual.upper()
            if actual != expected:
                raise RuntimeError(
                    f"stock_rank.csv {ticker} {field_name} mismatch: "
                    f"{actual!r} != {expected!r}"
                )

        rank_final_score = float(rank_row["FinalScore"])
        if not math.isclose(
            final_score, rank_final_score, rel_tol=0.0, abs_tol=1e-9
        ):
            raise RuntimeError(
                f"stock_rank.csv {ticker} FinalScore mismatch: "
                f"{rank_final_score} != {final_score}"
            )

        price = float(rank_row["Close"])
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError(f"stock_rank.csv {ticker} Close is invalid")

        why_tracked = str(rank_row["Reason"]).strip()
        if not why_tracked:
            raise RuntimeError(f"stock_rank.csv {ticker} Reason is missing")

        fundamental_score, combined_score = _optional_combined_values(
            ticker,
            run_id=run_id,
            as_of_date=as_of_date,
            universe_version=universe_version,
            score_model_version=score_model_version,
        )

        previews.append(
            {
                "Date": date.fromisoformat(as_of_date),
                "Ticker": ticker,
                "Signal": signal,
                "Rank": rank,
                "FinalScore": final_score,
                "FundamentalScore": fundamental_score,
                "CombinedScore": combined_score,
                "Price": price,
                "WhyTracked": why_tracked,
                "ResearchNote": None,
                "30D": None,
                "60D": None,
                "90D": None,
                "Outcome": "OPEN",
            }
        )

    return previews


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Observation Workbook authority mapper (dry-run only)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate production authorities and print Daily_Run plus "
            "Candidate_Tracking mappings"
        ),
    )
    args = parser.parse_args()

    if not args.dry_run:
        parser.error("Phase 2 supports --dry-run only; workbook writes are disabled")

    daily_preview = build_daily_run_preview()
    candidate_previews = build_candidate_tracking_previews()

    print("\nOBSERVATION RUNNER — DAILY_RUN DRY RUN")
    print("=" * 72)
    for key, value in daily_preview.items():
        print(f"{key:<20}: {value}")
    print("=" * 72)

    print("\nOBSERVATION RUNNER — CANDIDATE_TRACKING DRY RUN")
    print("=" * 72)
    if not candidate_previews:
        print("No BUY/WATCH candidates for this run.")
    else:
        for index, preview in enumerate(candidate_previews, start=1):
            if index > 1:
                print("-" * 72)
            for key, value in preview.items():
                print(f"{key:<20}: {value}")
    print("=" * 72)

    print("PASS: authority checks completed")
    print("NO WORKBOOK WRITE WAS PERFORMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
