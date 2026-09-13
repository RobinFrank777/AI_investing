from __future__ import annotations

from copy import copy
from datetime import date as date_type, datetime
from pathlib import Path
import shutil

from openpyxl import load_workbook


# ============================================================
# Configuration
# ============================================================

WORKBOOK_DIR = Path.home() / "Documents" / "AI_investing_observation"

SOURCE_FILE = WORKBOOK_DIR / "AI_investing_observation.xlsx"

TEST_FILE = WORKBOOK_DIR / "AI_investing_observation_test.xlsx"

DAILY_RUN_SHEET = "Daily_Run"

DAILY_RUN_HEADER_ROW = 4
DAILY_RUN_FIRST_DATA_ROW = 5

DAILY_RUN_HEADERS = [
    "Date",
    "Version",
    "PipelineStatus",
    "PassSteps",
    "RunId",
    "AsOfDate",
    "UniverseVersion",
    "ScoreModelVersion",
    "RiskModelVersion",
    "UniverseConfigured",
    "Ready",
    "Excluded",
    "ProviderRejected",
    "StaleMarketData",
    "InsufficientHistory",
    "ExcludedSymbols",
    "CoverageStatus",
    "BUY",
    "WATCH",
    "IGNORE",
    "FinalStatus",
    "Notes",
]

CANDIDATE_TRACKING_SHEET = "Candidate_Tracking"
CANDIDATE_TRACKING_HEADER_ROW = 4
CANDIDATE_TRACKING_FIRST_DATA_ROW = 5

CANDIDATE_TRACKING_HEADERS = [
    "Date",
    "Ticker",
    "Signal",
    "Rank",
    "FinalScore",
    "FundamentalScore",
    "CombinedScore",
    "Price",
    "WhyTracked",
    "ResearchNote",
    "30D",
    "60D",
    "90D",
    "Outcome",
]

DECISION_LOG_SHEET = "Decision_Log"
DECISION_LOG_HEADER_ROW = 4
DECISION_LOG_FIRST_DATA_ROW = 5

DECISION_LOG_HEADERS = [
    "Date",
    "Ticker",
    "SystemView",
    "MyView",
    "Action",
    "PositionBefore",
    "PositionAfter",
    "Reason",
    "ExpectedRisk",
    "ReviewDate",
    "Result",
]


REVIEW_LOG_SHEET = "Review_Log"
REVIEW_LOG_HEADER_ROW = 4
REVIEW_LOG_FIRST_DATA_ROW = 5

REVIEW_LOG_HEADERS = [
    "Date",
    "Ticker",
    "ReviewStatus",
    "ReviewReason",
    "PortfolioFlag",
    "RootCauseType",
    "ActionTaken",
    "Resolved",
    "ResolutionDate",
]

MAINTENANCE_LOG_SHEET = "Maintenance_Log"
MAINTENANCE_LOG_HEADER_ROW = 4
MAINTENANCE_LOG_FIRST_DATA_ROW = 5

MAINTENANCE_LOG_HEADERS = [
    "Date",
    "Category",
    "Severity",
    "Ticker/Scope",
    "Issue",
    "Evidence",
    "Action",
    "FileChanged",
    "Before",
    "After",
    "Result",
    "FollowUpDate",
    "Status",
    "Notes",
]

MAINTENANCE_LOG_CATEGORIES = {
    "MARKET_DATA",
    "UNIVERSE",
    "FUNDAMENTALS",
    "COMPANY_PROFILE",
    "PIPELINE",
    "REVIEW",
    "REPORT",
    "CONFIG",
    "ENVIRONMENT",
    "CODE_BUG",
    "DOCUMENTATION",
    "OTHER",
}

MAINTENANCE_LOG_SEVERITIES = {"P0", "P1", "P2", "P3"}
MAINTENANCE_LOG_STATUSES = {"OPEN", "MONITORING", "DEFERRED", "CLOSED"}


WEEKLY_REVIEW_SHEET = "Weekly_Review"
WEEKLY_REVIEW_HEADER_ROW = 4
WEEKLY_REVIEW_FIRST_DATA_ROW = 5

WEEKLY_REVIEW_HEADERS = [
    "Week",
    "PipelineReliability",
    "DataQuality",
    "BestCandidates",
    "ReviewIssues",
    "MaintenanceSummary",
    "InvestmentLessons",
    "NextWeekFocus",
]


MONTHLY_REVIEW_SHEET = "Monthly_Review"
MONTHLY_REVIEW_HEADER_ROW = 4
MONTHLY_REVIEW_FIRST_DATA_ROW = 5

MONTHLY_REVIEW_HEADERS = [
    "Month",
    "RunSuccessRate",
    "AvgReady",
    "MinReady",
    "BUYDays",
    "WATCHDays",
    "ReviewCount",
    "BlockedCount",
    "TopMaintenanceIssue",
    "SystemValue",
    "MainWeakness",
    "ChangeRecommended",
]

MONTHLY_REVIEW_CHANGE_RECOMMENDED = {
    "NO_CHANGE",
    "OBSERVE",
    "DATA_IMPROVEMENT",
    "DOCUMENTATION",
    "NEXT_VERSION_CANDIDATE",
}


# ============================================================
# Validation
# ============================================================

def validate_daily_run_schema(ws) -> None:
    """
    Confirm that Daily_Run still has the expected schema.

    Fail closed if the workbook structure has changed.
    """

    actual_headers = [
        ws.cell(row=DAILY_RUN_HEADER_ROW, column=col).value
        for col in range(1, len(DAILY_RUN_HEADERS) + 1)
    ]

    if actual_headers != DAILY_RUN_HEADERS:
        print("\nERROR: Daily_Run schema mismatch.")
        print("\nExpected:")
        print(DAILY_RUN_HEADERS)

        print("\nActual:")
        print(actual_headers)

        raise RuntimeError(
            "Daily_Run schema validation failed. Workbook was NOT modified."
        )


def _normalize_daily_run_date(value):
    """Normalize Excel/Python date values for duplicate-date checks."""

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date_type):
        return value

    if isinstance(value, str):
        try:
            return date_type.fromisoformat(value.strip())
        except ValueError:
            return value.strip()

    return value


def validate_daily_run_history_contiguous(ws) -> None:
    """
    Confirm that Daily_Run history is append-only with no internal blank row.

    A blank row followed by a later populated row indicates a history gap.
    Fail closed rather than backfilling an older position.
    """

    first_empty_row = None

    for row in range(DAILY_RUN_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(DAILY_RUN_HEADERS) + 1)
        ]

        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Daily_Run history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def validate_daily_run_duplicate(ws, date, run_id) -> None:
    """
    Reject a duplicate observation Date or RunId.

    Daily_Run policy is one record per day and RunId must be unique.
    """

    target_date = _normalize_daily_run_date(date)

    for row in range(DAILY_RUN_FIRST_DATA_ROW, ws.max_row + 1):
        existing_date = ws.cell(row=row, column=1).value
        existing_run_id = ws.cell(row=row, column=5).value

        if existing_date is None and existing_run_id is None:
            continue

        if _normalize_daily_run_date(existing_date) == target_date:
            raise RuntimeError(
                f"Duplicate Daily_Run Date detected: {target_date}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )

        if existing_run_id == run_id:
            raise RuntimeError(
                f"Duplicate Daily_Run RunId detected: {run_id}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_daily_run_values(
    *,
    universe_configured,
    ready,
    excluded,
    buy,
    watch,
    ignore,
) -> None:
    """Validate internal Daily_Run arithmetic consistency."""

    if ready + excluded != universe_configured:
        raise RuntimeError(
            "Daily_Run value validation failed: "
            f"Ready({ready}) + Excluded({excluded}) "
            f"!= UniverseConfigured({universe_configured}). "
            "Workbook was NOT modified."
        )

    if buy + watch + ignore != ready:
        raise RuntimeError(
            "Daily_Run value validation failed: "
            f"BUY({buy}) + WATCH({watch}) + IGNORE({ignore}) "
            f"!= Ready({ready}). "
            "Workbook was NOT modified."
        )


# ============================================================
# Row discovery
# ============================================================

def find_first_empty_daily_run_row(ws) -> int:
    """
    Find the first truly empty Daily_Run data row.

    Do NOT rely on ws.max_row because the workbook contains
    preformatted / reserved rows.
    """

    for row in range(DAILY_RUN_FIRST_DATA_ROW, ws.max_row + 2):

        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(DAILY_RUN_HEADERS) + 1)
        ]

        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Daily_Run row found.")


# ============================================================
# Candidate_Tracking validation / row discovery
# ============================================================

def validate_candidate_tracking_schema(ws) -> None:
    """Fail closed if Candidate_Tracking headers changed."""

    actual_headers = [
        ws.cell(row=CANDIDATE_TRACKING_HEADER_ROW, column=col).value
        for col in range(1, len(CANDIDATE_TRACKING_HEADERS) + 1)
    ]

    if actual_headers != CANDIDATE_TRACKING_HEADERS:
        print("\nERROR: Candidate_Tracking schema mismatch.")
        print("\nExpected:")
        print(CANDIDATE_TRACKING_HEADERS)
        print("\nActual:")
        print(actual_headers)
        raise RuntimeError(
            "Candidate_Tracking schema validation failed. Workbook was NOT modified."
        )


def validate_candidate_tracking_history_contiguous(ws) -> None:
    """Reject an empty historical row followed by later populated rows."""

    first_empty_row = None

    for row in range(CANDIDATE_TRACKING_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(CANDIDATE_TRACKING_HEADERS) + 1)
        ]
        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Candidate_Tracking history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def validate_candidate_tracking_duplicate(ws, date, ticker) -> None:
    """Reject duplicate Date + Ticker; the same ticker may reappear on later dates."""

    target_date = _normalize_daily_run_date(date)
    target_ticker = str(ticker).strip().upper()

    if not target_ticker:
        raise RuntimeError("Candidate_Tracking Ticker must not be empty.")

    for row in range(CANDIDATE_TRACKING_FIRST_DATA_ROW, ws.max_row + 1):
        existing_date = ws.cell(row=row, column=1).value
        existing_ticker = ws.cell(row=row, column=2).value

        if existing_date is None and existing_ticker is None:
            continue

        try:
            existing_day = _normalize_daily_run_date(existing_date)
        except RuntimeError:
            continue

        existing_symbol = str(existing_ticker or "").strip().upper()

        if existing_day == target_date and existing_symbol == target_ticker:
            raise RuntimeError(
                "Duplicate Candidate_Tracking Date + Ticker detected: "
                f"{target_date.isoformat()} / {target_ticker}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_candidate_tracking_values(
    *, ticker, signal, rank, final_score, price, outcome
) -> None:
    """Validate only stable, low-risk Candidate_Tracking invariants."""

    if not str(ticker).strip():
        raise RuntimeError("Candidate_Tracking Ticker must not be empty.")

    if not str(signal).strip():
        raise RuntimeError("Candidate_Tracking Signal must not be empty.")

    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
        raise RuntimeError("Candidate_Tracking Rank must be a positive integer.")

    if not isinstance(final_score, (int, float)) or isinstance(final_score, bool):
        raise RuntimeError("Candidate_Tracking FinalScore must be numeric.")

    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        raise RuntimeError("Candidate_Tracking Price must be a positive number.")

    if not str(outcome).strip():
        raise RuntimeError("Candidate_Tracking Outcome must not be empty.")


def find_first_empty_candidate_tracking_row(ws) -> int:
    """Find the first truly empty Candidate_Tracking row."""

    for row in range(CANDIDATE_TRACKING_FIRST_DATA_ROW, ws.max_row + 2):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(CANDIDATE_TRACKING_HEADERS) + 1)
        ]
        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Candidate_Tracking row found.")


def copy_candidate_tracking_row_format(ws, source_row: int, target_row: int) -> None:
    """Copy Candidate_Tracking formatting only; never copy historical values."""

    for col in range(1, len(CANDIDATE_TRACKING_HEADERS) + 1):
        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height




# ============================================================
# Decision_Log validation / row discovery
# ============================================================

def validate_decision_log_schema(ws) -> None:
    """Fail closed if Decision_Log headers changed."""

    actual_headers = [
        ws.cell(row=DECISION_LOG_HEADER_ROW, column=col).value
        for col in range(1, len(DECISION_LOG_HEADERS) + 1)
    ]

    if actual_headers != DECISION_LOG_HEADERS:
        print("\nERROR: Decision_Log schema mismatch.")
        print("\nExpected:")
        print(DECISION_LOG_HEADERS)
        print("\nActual:")
        print(actual_headers)
        raise RuntimeError(
            "Decision_Log schema validation failed. Workbook was NOT modified."
        )


def validate_decision_log_history_contiguous(ws) -> None:
    """Reject an empty historical row followed by later populated rows."""

    first_empty_row = None

    for row in range(DECISION_LOG_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(DECISION_LOG_HEADERS) + 1)
        ]
        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Decision_Log history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def validate_decision_log_duplicate(ws, date, ticker, action) -> None:
    """Reject duplicate Date + Ticker + Action decisions."""

    target_date = _normalize_daily_run_date(date)
    target_ticker = str(ticker or "").strip().upper()
    target_action = str(action or "").strip().upper()

    for row in range(DECISION_LOG_FIRST_DATA_ROW, ws.max_row + 1):
        existing_date = ws.cell(row=row, column=1).value
        existing_ticker = ws.cell(row=row, column=2).value
        existing_action = ws.cell(row=row, column=5).value

        if existing_date is None and existing_ticker is None and existing_action is None:
            continue

        existing_day = _normalize_daily_run_date(existing_date)
        existing_symbol = str(existing_ticker or "").strip().upper()
        existing_action_norm = str(existing_action or "").strip().upper()

        if (
            existing_day == target_date
            and existing_symbol == target_ticker
            and existing_action_norm == target_action
        ):
            raise RuntimeError(
                "Duplicate Decision_Log Date + Ticker + Action detected: "
                f"{target_date} / {target_ticker or '<BLANK>'} / {target_action}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_decision_log_values(*, date, system_view, my_view, action, reason) -> None:
    """Validate stable, low-risk Decision_Log invariants."""

    if _normalize_daily_run_date(date) in (None, ""):
        raise RuntimeError("Decision_Log Date must not be empty.")

    if not str(system_view or "").strip():
        raise RuntimeError("Decision_Log SystemView must not be empty.")

    if not str(my_view or "").strip():
        raise RuntimeError("Decision_Log MyView must not be empty.")

    if not str(action or "").strip():
        raise RuntimeError("Decision_Log Action must not be empty.")

    if not str(reason or "").strip():
        raise RuntimeError("Decision_Log Reason must not be empty.")


def find_first_empty_decision_log_row(ws) -> int:
    """Find the first truly empty Decision_Log row."""

    for row in range(DECISION_LOG_FIRST_DATA_ROW, ws.max_row + 2):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(DECISION_LOG_HEADERS) + 1)
        ]
        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Decision_Log row found.")


def copy_decision_log_row_format(ws, source_row: int, target_row: int) -> None:
    """Copy Decision_Log formatting only; never copy historical values."""

    for col in range(1, len(DECISION_LOG_HEADERS) + 1):
        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height



# ============================================================
# Review_Log validation / row discovery
# ============================================================

def validate_review_log_schema(ws) -> None:
    """Fail closed if Review_Log headers changed."""

    actual_headers = [
        ws.cell(row=REVIEW_LOG_HEADER_ROW, column=col).value
        for col in range(1, len(REVIEW_LOG_HEADERS) + 1)
    ]

    if actual_headers != REVIEW_LOG_HEADERS:
        print("\nERROR: Review_Log schema mismatch.")
        print("\nExpected:")
        print(REVIEW_LOG_HEADERS)
        print("\nActual:")
        print(actual_headers)
        raise RuntimeError(
            "Review_Log schema validation failed. Workbook was NOT modified."
        )


def validate_review_log_history_contiguous(ws) -> None:
    """Reject an empty historical row followed by later populated rows."""

    first_empty_row = None

    for row in range(REVIEW_LOG_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(REVIEW_LOG_HEADERS) + 1)
        ]
        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Review_Log history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def validate_review_log_duplicate(ws, date, ticker, review_status) -> None:
    """Reject duplicate Date + Ticker + ReviewStatus records."""

    target_date = _normalize_daily_run_date(date)
    target_ticker = str(ticker or "").strip().upper()
    target_status = str(review_status or "").strip().upper()

    for row in range(REVIEW_LOG_FIRST_DATA_ROW, ws.max_row + 1):
        existing_date = ws.cell(row=row, column=1).value
        existing_ticker = ws.cell(row=row, column=2).value
        existing_status = ws.cell(row=row, column=3).value

        if existing_date is None and existing_ticker is None and existing_status is None:
            continue

        existing_day = _normalize_daily_run_date(existing_date)
        existing_symbol = str(existing_ticker or "").strip().upper()
        existing_status_norm = str(existing_status or "").strip().upper()

        if (
            existing_day == target_date
            and existing_symbol == target_ticker
            and existing_status_norm == target_status
        ):
            raise RuntimeError(
                "Duplicate Review_Log Date + Ticker + ReviewStatus detected: "
                f"{target_date} / {target_ticker or '<BLANK>'} / {target_status}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_review_log_values(
    *,
    date,
    review_status,
    review_reason,
    portfolio_flag,
    action_taken,
    resolved,
) -> None:
    """Validate stable, low-risk Review_Log invariants."""

    if _normalize_daily_run_date(date) in (None, ""):
        raise RuntimeError("Review_Log Date must not be empty.")

    if not str(review_status or "").strip():
        raise RuntimeError("Review_Log ReviewStatus must not be empty.")

    if not str(review_reason or "").strip():
        raise RuntimeError("Review_Log ReviewReason must not be empty.")

    if not str(portfolio_flag or "").strip():
        raise RuntimeError("Review_Log PortfolioFlag must not be empty.")

    if not str(action_taken or "").strip():
        raise RuntimeError("Review_Log ActionTaken must not be empty.")

    if isinstance(resolved, bool):
        return

    normalized = str(resolved or "").strip().upper()
    if normalized not in {"YES", "NO", "TRUE", "FALSE"}:
        raise RuntimeError(
            "Review_Log Resolved must be boolean or one of YES/NO/TRUE/FALSE."
        )


def find_first_empty_review_log_row(ws) -> int:
    """Find the first truly empty Review_Log row."""

    for row in range(REVIEW_LOG_FIRST_DATA_ROW, ws.max_row + 2):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(REVIEW_LOG_HEADERS) + 1)
        ]
        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Review_Log row found.")


def copy_review_log_row_format(ws, source_row: int, target_row: int) -> None:
    """Copy Review_Log formatting only; never copy historical values."""

    for col in range(1, len(REVIEW_LOG_HEADERS) + 1):
        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height


# ============================================================
# Maintenance_Log validation / row discovery
# ============================================================

def validate_maintenance_log_schema(ws) -> None:
    """Fail closed if Maintenance_Log headers changed."""

    actual_headers = [
        ws.cell(row=MAINTENANCE_LOG_HEADER_ROW, column=col).value
        for col in range(1, len(MAINTENANCE_LOG_HEADERS) + 1)
    ]

    if actual_headers != MAINTENANCE_LOG_HEADERS:
        print("\nERROR: Maintenance_Log schema mismatch.")
        print("\nExpected:")
        print(MAINTENANCE_LOG_HEADERS)
        print("\nActual:")
        print(actual_headers)
        raise RuntimeError(
            "Maintenance_Log schema validation failed. Workbook was NOT modified."
        )


def validate_maintenance_log_history_contiguous(ws) -> None:
    """Reject an empty historical row followed by later populated rows."""

    first_empty_row = None

    for row in range(MAINTENANCE_LOG_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(MAINTENANCE_LOG_HEADERS) + 1)
        ]
        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Maintenance_Log history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def validate_maintenance_log_duplicate(
    ws, date, category, ticker_scope, issue
) -> None:
    """Reject duplicate Date + Category + Ticker/Scope + Issue records."""

    target_date = _normalize_daily_run_date(date)
    target_category = str(category or "").strip().upper()
    target_scope = str(ticker_scope or "").strip().upper()
    target_issue = str(issue or "").strip()

    for row in range(MAINTENANCE_LOG_FIRST_DATA_ROW, ws.max_row + 1):
        existing_date = ws.cell(row=row, column=1).value
        existing_category = ws.cell(row=row, column=2).value
        existing_scope = ws.cell(row=row, column=4).value
        existing_issue = ws.cell(row=row, column=5).value

        if (
            existing_date is None
            and existing_category is None
            and existing_scope is None
            and existing_issue is None
        ):
            continue

        existing_day = _normalize_daily_run_date(existing_date)
        existing_category_norm = str(existing_category or "").strip().upper()
        existing_scope_norm = str(existing_scope or "").strip().upper()
        existing_issue_norm = str(existing_issue or "").strip()

        if (
            existing_day == target_date
            and existing_category_norm == target_category
            and existing_scope_norm == target_scope
            and existing_issue_norm == target_issue
        ):
            raise RuntimeError(
                "Duplicate Maintenance_Log record detected: "
                f"{target_date} / {target_category} / {target_scope} / {target_issue}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_maintenance_log_values(
    *,
    date,
    category,
    severity,
    ticker_scope,
    issue,
    evidence,
    status,
) -> None:
    """Validate stable Maintenance_Log governance invariants."""

    if _normalize_daily_run_date(date) in (None, ""):
        raise RuntimeError("Maintenance_Log Date must not be empty.")

    category_norm = str(category or "").strip().upper()
    if category_norm not in MAINTENANCE_LOG_CATEGORIES:
        raise RuntimeError(
            "Maintenance_Log Category must be one of: "
            + ", ".join(sorted(MAINTENANCE_LOG_CATEGORIES))
        )

    severity_norm = str(severity or "").strip().upper()
    if severity_norm not in MAINTENANCE_LOG_SEVERITIES:
        raise RuntimeError(
            "Maintenance_Log Severity must be one of P0/P1/P2/P3."
        )

    if not str(ticker_scope or "").strip():
        raise RuntimeError("Maintenance_Log Ticker/Scope must not be empty.")

    if not str(issue or "").strip():
        raise RuntimeError("Maintenance_Log Issue must not be empty.")

    if not str(evidence or "").strip():
        raise RuntimeError("Maintenance_Log Evidence must not be empty.")

    status_norm = str(status or "").strip().upper()
    if status_norm not in MAINTENANCE_LOG_STATUSES:
        raise RuntimeError(
            "Maintenance_Log Status must be one of OPEN/MONITORING/DEFERRED/CLOSED."
        )


def find_first_empty_maintenance_log_row(ws) -> int:
    """Find the first truly empty Maintenance_Log row."""

    for row in range(MAINTENANCE_LOG_FIRST_DATA_ROW, ws.max_row + 2):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(MAINTENANCE_LOG_HEADERS) + 1)
        ]
        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Maintenance_Log row found.")


def copy_maintenance_log_row_format(ws, source_row: int, target_row: int) -> None:
    """Copy Maintenance_Log formatting only; never copy historical values."""

    for col in range(1, len(MAINTENANCE_LOG_HEADERS) + 1):
        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height



# ============================================================
# Weekly_Review validation / row discovery
# ============================================================

def validate_weekly_review_schema(ws) -> None:
    """Fail closed if Weekly_Review headers changed."""

    actual_headers = [
        ws.cell(row=WEEKLY_REVIEW_HEADER_ROW, column=col).value
        for col in range(1, len(WEEKLY_REVIEW_HEADERS) + 1)
    ]

    if actual_headers != WEEKLY_REVIEW_HEADERS:
        print("\nERROR: Weekly_Review schema mismatch.")
        print("\nExpected:")
        print(WEEKLY_REVIEW_HEADERS)
        print("\nActual:")
        print(actual_headers)
        raise RuntimeError(
            "Weekly_Review schema validation failed. Workbook was NOT modified."
        )


def validate_weekly_review_history_contiguous(ws) -> None:
    """Reject an empty historical row followed by later populated rows."""

    first_empty_row = None

    for row in range(WEEKLY_REVIEW_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(WEEKLY_REVIEW_HEADERS) + 1)
        ]
        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Weekly_Review history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def _normalize_week_key(week) -> str:
    """Normalize the weekly key while preserving the workbook's human-readable format."""

    normalized = " ".join(str(week or "").strip().split())
    if not normalized:
        raise RuntimeError("Weekly_Review Week must not be empty.")
    return normalized


def validate_weekly_review_duplicate(ws, week) -> None:
    """Reject duplicate Week records; Weekly_Review allows one record per week."""

    target_week = _normalize_week_key(week)

    for row in range(WEEKLY_REVIEW_FIRST_DATA_ROW, ws.max_row + 1):
        existing_week = ws.cell(row=row, column=1).value

        if existing_week is None:
            continue

        if _normalize_week_key(existing_week) == target_week:
            raise RuntimeError(
                f"Duplicate Weekly_Review Week detected: {target_week}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_weekly_review_values(
    *,
    week,
    pipeline_reliability,
    data_quality,
    best_candidates,
    review_issues,
    maintenance_summary,
    investment_lessons,
    next_week_focus,
) -> None:
    """Validate stable Weekly_Review invariants without interpreting review content."""

    _normalize_week_key(week)

    required_text_fields = {
        "PipelineReliability": pipeline_reliability,
        "DataQuality": data_quality,
        "BestCandidates": best_candidates,
        "ReviewIssues": review_issues,
        "MaintenanceSummary": maintenance_summary,
        "InvestmentLessons": investment_lessons,
        "NextWeekFocus": next_week_focus,
    }

    for field_name, value in required_text_fields.items():
        if not str(value or "").strip():
            raise RuntimeError(
                f"Weekly_Review {field_name} must not be empty."
            )


def find_first_empty_weekly_review_row(ws) -> int:
    """Find the first truly empty Weekly_Review row."""

    for row in range(WEEKLY_REVIEW_FIRST_DATA_ROW, ws.max_row + 2):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(WEEKLY_REVIEW_HEADERS) + 1)
        ]
        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Weekly_Review row found.")


def copy_weekly_review_row_format(ws, source_row: int, target_row: int) -> None:
    """Copy Weekly_Review formatting only; never copy historical values."""

    for col in range(1, len(WEEKLY_REVIEW_HEADERS) + 1):
        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height



# ============================================================
# Monthly_Review validation / row discovery
# ============================================================

def validate_monthly_review_schema(ws) -> None:
    """Fail closed if Monthly_Review headers changed."""

    actual_headers = [
        ws.cell(row=MONTHLY_REVIEW_HEADER_ROW, column=col).value
        for col in range(1, len(MONTHLY_REVIEW_HEADERS) + 1)
    ]

    if actual_headers != MONTHLY_REVIEW_HEADERS:
        print("\nERROR: Monthly_Review schema mismatch.")
        print("\nExpected:")
        print(MONTHLY_REVIEW_HEADERS)
        print("\nActual:")
        print(actual_headers)
        raise RuntimeError(
            "Monthly_Review schema validation failed. Workbook was NOT modified."
        )


def validate_monthly_review_history_contiguous(ws) -> None:
    """Reject an empty historical row followed by later populated rows."""

    first_empty_row = None

    for row in range(MONTHLY_REVIEW_FIRST_DATA_ROW, ws.max_row + 1):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(MONTHLY_REVIEW_HEADERS) + 1)
        ]
        row_is_empty = all(value is None for value in values)

        if row_is_empty:
            if first_empty_row is None:
                first_empty_row = row
            continue

        if first_empty_row is not None:
            raise RuntimeError(
                "Monthly_Review history gap detected: "
                f"row {first_empty_row} is empty but row {row} contains data. "
                "Workbook was NOT modified."
            )


def _normalize_month_key(month) -> str:
    """Normalize Month to YYYY-MM."""

    if isinstance(month, datetime):
        return f"{month.year:04d}-{month.month:02d}"

    if isinstance(month, date_type):
        return f"{month.year:04d}-{month.month:02d}"

    normalized = str(month or "").strip()

    if (
        len(normalized) == 7
        and normalized[4] == "-"
        and normalized[:4].isdigit()
        and normalized[5:].isdigit()
    ):
        month_number = int(normalized[5:])
        if 1 <= month_number <= 12:
            return f"{int(normalized[:4]):04d}-{month_number:02d}"

    raise RuntimeError(
        "Monthly_Review Month must use YYYY-MM format, for example 2026-09."
    )


def validate_monthly_review_duplicate(ws, month) -> None:
    """Reject duplicate Month records; Monthly_Review allows one record per month."""

    target_month = _normalize_month_key(month)

    for row in range(MONTHLY_REVIEW_FIRST_DATA_ROW, ws.max_row + 1):
        existing_month = ws.cell(row=row, column=1).value

        if existing_month is None:
            continue

        if _normalize_month_key(existing_month) == target_month:
            raise RuntimeError(
                f"Duplicate Monthly_Review Month detected: {target_month}. "
                f"Existing row: {row}. Workbook was NOT modified."
            )


def validate_monthly_review_values(
    *,
    month,
    run_success_rate,
    avg_ready,
    min_ready,
    buy_days,
    watch_days,
    review_count,
    blocked_count,
    top_maintenance_issue,
    system_value,
    main_weakness,
    change_recommended,
) -> None:
    """Validate stable Monthly_Review invariants without interpreting conclusions."""

    _normalize_month_key(month)

    if not str(run_success_rate or "").strip():
        raise RuntimeError("Monthly_Review RunSuccessRate must not be empty.")

    numeric_fields = {
        "AvgReady": avg_ready,
        "MinReady": min_ready,
        "BUYDays": buy_days,
        "WATCHDays": watch_days,
        "ReviewCount": review_count,
        "BlockedCount": blocked_count,
    }

    for field_name, value in numeric_fields.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"Monthly_Review {field_name} must be numeric.")
        if value < 0:
            raise RuntimeError(f"Monthly_Review {field_name} must not be negative.")

    required_text_fields = {
        "TopMaintenanceIssue": top_maintenance_issue,
        "SystemValue": system_value,
        "MainWeakness": main_weakness,
    }

    for field_name, value in required_text_fields.items():
        if not str(value or "").strip():
            raise RuntimeError(f"Monthly_Review {field_name} must not be empty.")

    change_norm = str(change_recommended or "").strip().upper()
    if change_norm not in MONTHLY_REVIEW_CHANGE_RECOMMENDED:
        raise RuntimeError(
            "Monthly_Review ChangeRecommended must be one of: "
            + ", ".join(sorted(MONTHLY_REVIEW_CHANGE_RECOMMENDED))
        )


def find_first_empty_monthly_review_row(ws) -> int:
    """Find the first truly empty Monthly_Review row."""

    for row in range(MONTHLY_REVIEW_FIRST_DATA_ROW, ws.max_row + 2):
        values = [
            ws.cell(row=row, column=col).value
            for col in range(1, len(MONTHLY_REVIEW_HEADERS) + 1)
        ]
        if all(value is None for value in values):
            return row

    raise RuntimeError("No empty Monthly_Review row found.")


def copy_monthly_review_row_format(ws, source_row: int, target_row: int) -> None:
    """Copy Monthly_Review formatting only; never copy historical values."""

    for col in range(1, len(MONTHLY_REVIEW_HEADERS) + 1):
        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height


# ============================================================
# Formatting
# ============================================================

def copy_row_format(ws, source_row: int, target_row: int) -> None:
    """
    Copy formatting only.
    Do NOT copy historical values.
    """

    for col in range(1, len(DAILY_RUN_HEADERS) + 1):

        source_cell = ws.cell(row=source_row, column=col)
        target_cell = ws.cell(row=target_row, column=col)

        if source_cell.has_style:
            target_cell._style = copy(source_cell._style)

        if source_cell.number_format:
            target_cell.number_format = source_cell.number_format

        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

    if ws.row_dimensions[source_row].height:
        ws.row_dimensions[target_row].height = (
            ws.row_dimensions[source_row].height
        )


# ============================================================
# Backup
# ============================================================

def make_backup(file_path: Path) -> Path:

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    backup_path = file_path.with_name(
        f"{file_path.stem}.backup-{timestamp}{file_path.suffix}"
    )

    shutil.copy2(file_path, backup_path)

    print(f"Backup created: {backup_path}")

    return backup_path


# ============================================================
# Daily_Run writer
# ============================================================

def append_daily_run(
    file_path: Path,
    *,
    date,
    version,
    pipeline_status,
    pass_steps,
    run_id,
    as_of_date,
    universe_version,
    score_model_version,
    risk_model_version,
    universe_configured,
    ready,
    excluded,
    provider_rejected,
    stale_market_data,
    insufficient_history,
    excluded_symbols,
    coverage_status,
    buy,
    watch,
    ignore,
    final_status,
    notes,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    wb = load_workbook(file_path)

    if DAILY_RUN_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{DAILY_RUN_SHEET}' does not exist."
        )

    ws = wb[DAILY_RUN_SHEET]

    # --------------------------------------------------------
    # Schema validation
    # --------------------------------------------------------

    validate_daily_run_schema(ws)
    validate_daily_run_history_contiguous(ws)
    validate_daily_run_duplicate(
        ws,
        date=date,
        run_id=run_id,
    )
    validate_daily_run_values(
        universe_configured=universe_configured,
        ready=ready,
        excluded=excluded,
        buy=buy,
        watch=watch,
        ignore=ignore,
    )

    # --------------------------------------------------------
    # Find safe append row
    # --------------------------------------------------------

    target_row = find_first_empty_daily_run_row(ws)

    # Preserve formatting using previous populated row
    previous_row = target_row - 1

    if previous_row >= DAILY_RUN_FIRST_DATA_ROW:
        copy_row_format(ws, previous_row, target_row)

    # --------------------------------------------------------
    # Prepare values
    # --------------------------------------------------------

    values = [
        date,
        version,
        pipeline_status,
        pass_steps,
        run_id,
        as_of_date,
        universe_version,
        score_model_version,
        risk_model_version,
        universe_configured,
        ready,
        excluded,
        provider_rejected,
        stale_market_data,
        insufficient_history,
        excluded_symbols,
        coverage_status,
        buy,
        watch,
        ignore,
        final_status,
        notes,
    ]

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    wb.save(file_path)

    # --------------------------------------------------------
    # Verification: reopen
    # --------------------------------------------------------

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[DAILY_RUN_SHEET]

    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(DAILY_RUN_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError(
            "Post-save verification failed."
        )

    print("\nDaily_Run append PASS")
    print(f"Workbook : {file_path}")
    print(f"Sheet    : {DAILY_RUN_SHEET}")
    print(f"Row      : {target_row}")
    print(f"Date     : {date}")
    print(f"RunId    : {run_id}")
    print(f"READY    : {ready}/{universe_configured}")
    print(f"Status   : {final_status}")

    return target_row


# ============================================================
# Candidate_Tracking writer
# ============================================================

def append_candidate_tracking(
    file_path: Path,
    *,
    date,
    ticker,
    signal,
    rank,
    final_score,
    fundamental_score,
    combined_score,
    price,
    why_tracked,
    research_note,
    day_30,
    day_60,
    day_90,
    outcome,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    wb = load_workbook(file_path)

    if CANDIDATE_TRACKING_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{CANDIDATE_TRACKING_SHEET}' does not exist."
        )

    ws = wb[CANDIDATE_TRACKING_SHEET]

    validate_candidate_tracking_schema(ws)
    validate_candidate_tracking_history_contiguous(ws)
    validate_candidate_tracking_duplicate(ws, date, ticker)
    validate_candidate_tracking_values(
        ticker=ticker,
        signal=signal,
        rank=rank,
        final_score=final_score,
        price=price,
        outcome=outcome,
    )

    target_row = find_first_empty_candidate_tracking_row(ws)
    previous_row = target_row - 1

    if previous_row >= CANDIDATE_TRACKING_FIRST_DATA_ROW:
        copy_candidate_tracking_row_format(ws, previous_row, target_row)

    values = [
        date,
        str(ticker).strip().upper(),
        signal,
        rank,
        final_score,
        fundamental_score,
        combined_score,
        price,
        why_tracked,
        research_note,
        day_30,
        day_60,
        day_90,
        outcome,
    ]

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[CANDIDATE_TRACKING_SHEET]
    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(CANDIDATE_TRACKING_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError("Candidate_Tracking post-save verification failed.")

    print("\nCandidate_Tracking append PASS")
    print(f"Workbook : {file_path}")
    print(f"Sheet    : {CANDIDATE_TRACKING_SHEET}")
    print(f"Row      : {target_row}")
    print(f"Date     : {date}")
    print(f"Ticker   : {str(ticker).strip().upper()}")
    print(f"Signal   : {signal}")
    print(f"Rank     : {rank}")
    print(f"Score    : {final_score}")
    print(f"Outcome  : {outcome}")

    return target_row


# ============================================================
# Candidate_Tracking controlled outcome update
# ============================================================

CANDIDATE_TRACKING_MUTABLE_FIELDS = {
    "30D": 11,
    "60D": 12,
    "90D": 13,
    "Outcome": 14,
}

CANDIDATE_TRACKING_PROTECTED_COLUMNS = tuple(range(1, 11))


def _candidate_tracking_find_row(ws, date, ticker) -> int:
    """Locate exactly one Candidate_Tracking row by Date + Ticker."""

    target_date = _normalize_daily_run_date(date)
    target_ticker = str(ticker).strip().upper()

    if not target_ticker:
        raise RuntimeError("Candidate_Tracking Ticker must not be empty.")

    matches = []

    for row in range(CANDIDATE_TRACKING_FIRST_DATA_ROW, ws.max_row + 1):
        existing_date = ws.cell(row=row, column=1).value
        existing_ticker = ws.cell(row=row, column=2).value

        if existing_date is None and existing_ticker is None:
            continue

        existing_day = _normalize_daily_run_date(existing_date)
        existing_symbol = str(existing_ticker or "").strip().upper()

        if existing_day == target_date and existing_symbol == target_ticker:
            matches.append(row)

    if not matches:
        raise RuntimeError(
            "Candidate_Tracking row not found for "
            f"{target_date} / {target_ticker}. Workbook was NOT modified."
        )

    if len(matches) != 1:
        raise RuntimeError(
            "Candidate_Tracking key is not unique for "
            f"{target_date} / {target_ticker}: rows {matches}. "
            "Workbook was NOT modified."
        )

    return matches[0]


def _validate_candidate_outcome_value(field_name: str, value) -> None:
    """Validate values allowed in the controlled outcome fields."""

    if field_name in {"30D", "60D", "90D"}:
        if value is not None and (
            not isinstance(value, (int, float)) or isinstance(value, bool)
        ):
            raise RuntimeError(
                f"Candidate_Tracking {field_name} must be numeric or None."
            )

    elif field_name == "Outcome":
        if value is not None and not str(value).strip():
            raise RuntimeError(
                "Candidate_Tracking Outcome must be a non-empty string or None."
            )


def _validate_candidate_horizon_maturity(
    signal_date,
    evaluation_date,
    *,
    day_30,
    day_60,
    day_90,
) -> None:
    """Do not allow 30D/60D/90D values before their calendar-day horizon matures."""

    signal_day = _normalize_daily_run_date(signal_date)
    evaluation_day = _normalize_daily_run_date(evaluation_date)

    if not isinstance(signal_day, date_type) or not isinstance(evaluation_day, date_type):
        raise RuntimeError(
            "Candidate_Tracking maturity validation requires valid dates."
        )

    if evaluation_day < signal_day:
        raise RuntimeError(
            "Candidate_Tracking evaluation date cannot precede signal date."
        )

    elapsed_days = (evaluation_day - signal_day).days

    required = {
        "30D": (day_30, 30),
        "60D": (day_60, 60),
        "90D": (day_90, 90),
    }

    for field_name, (value, minimum_days) in required.items():
        if value is not None and elapsed_days < minimum_days:
            raise RuntimeError(
                f"Candidate_Tracking {field_name} is not mature: "
                f"only {elapsed_days} calendar days have elapsed; "
                f"requires at least {minimum_days}. Workbook was NOT modified."
            )


def update_candidate_outcome(
    file_path: Path,
    *,
    date,
    ticker,
    evaluation_date,
    day_30=None,
    day_60=None,
    day_90=None,
    outcome=None,
    overwrite: bool = False,
    create_backup: bool = True,
) -> int:
    """
    Controlled update for Candidate_Tracking outcome fields only.

    The immutable research snapshot (Date through ResearchNote) is never changed.
    By default, an already populated 30D/60D/90D/Outcome value cannot be overwritten.
    """

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    updates = {
        "30D": day_30,
        "60D": day_60,
        "90D": day_90,
        "Outcome": outcome,
    }

    if all(value is None for value in updates.values()):
        raise RuntimeError(
            "Candidate_Tracking outcome update requires at least one value."
        )

    for field_name, value in updates.items():
        _validate_candidate_outcome_value(field_name, value)

    _validate_candidate_horizon_maturity(
        date,
        evaluation_date,
        day_30=day_30,
        day_60=day_60,
        day_90=day_90,
    )

    wb = load_workbook(file_path)

    if CANDIDATE_TRACKING_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{CANDIDATE_TRACKING_SHEET}' does not exist."
        )

    ws = wb[CANDIDATE_TRACKING_SHEET]

    validate_candidate_tracking_schema(ws)
    validate_candidate_tracking_history_contiguous(ws)

    target_row = _candidate_tracking_find_row(ws, date, ticker)

    protected_before = [
        ws.cell(row=target_row, column=col).value
        for col in CANDIDATE_TRACKING_PROTECTED_COLUMNS
    ]

    for field_name, value in updates.items():
        if value is None:
            continue

        col = CANDIDATE_TRACKING_MUTABLE_FIELDS[field_name]
        existing_value = ws.cell(row=target_row, column=col).value

        allow_open_transition = (
            field_name == "Outcome"
            and isinstance(existing_value, str)
            and existing_value.strip().upper() == "OPEN"
            and str(value).strip().upper() != "OPEN"
        )

        if existing_value is not None and not overwrite and not allow_open_transition:
            raise RuntimeError(
                f"Candidate_Tracking {field_name} already contains "
                f"{existing_value!r} at row {target_row}. "
                "Use overwrite=True only after explicit review. "
                "Workbook was NOT modified."
            )

    if create_backup:
        make_backup(file_path)

    for field_name, value in updates.items():
        if value is None:
            continue

        col = CANDIDATE_TRACKING_MUTABLE_FIELDS[field_name]
        if field_name == "Outcome":
            value = str(value).strip()
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[CANDIDATE_TRACKING_SHEET]

    protected_after = [
        verify_ws.cell(row=target_row, column=col).value
        for col in CANDIDATE_TRACKING_PROTECTED_COLUMNS
    ]

    if protected_after != protected_before:
        raise RuntimeError(
            "Candidate_Tracking protected historical fields changed unexpectedly."
        )

    for field_name, value in updates.items():
        if value is None:
            continue

        col = CANDIDATE_TRACKING_MUTABLE_FIELDS[field_name]
        expected = str(value).strip() if field_name == "Outcome" else value
        actual = verify_ws.cell(row=target_row, column=col).value

        if actual != expected:
            raise RuntimeError(
                f"Candidate_Tracking {field_name} post-save verification failed."
            )

    print("\nCandidate_Tracking outcome update PASS")
    print(f"Workbook : {file_path}")
    print(f"Sheet    : {CANDIDATE_TRACKING_SHEET}")
    print(f"Row      : {target_row}")
    print(f"Date     : {date}")
    print(f"Ticker   : {str(ticker).strip().upper()}")
    print(f"EvalDate : {evaluation_date}")
    print(f"30D      : {day_30}")
    print(f"60D      : {day_60}")
    print(f"90D      : {day_90}")
    print(f"Outcome  : {outcome}")

    return target_row




# ============================================================
# Decision_Log writer
# ============================================================

def append_decision_log(
    file_path: Path,
    *,
    date,
    ticker,
    system_view,
    my_view,
    action,
    position_before,
    position_after,
    reason,
    expected_risk,
    review_date,
    result,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    wb = load_workbook(file_path)

    if DECISION_LOG_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{DECISION_LOG_SHEET}' does not exist."
        )

    ws = wb[DECISION_LOG_SHEET]

    validate_decision_log_schema(ws)
    validate_decision_log_history_contiguous(ws)
    validate_decision_log_duplicate(ws, date, ticker, action)
    validate_decision_log_values(
        date=date,
        system_view=system_view,
        my_view=my_view,
        action=action,
        reason=reason,
    )

    target_row = find_first_empty_decision_log_row(ws)
    previous_row = target_row - 1

    # Row 5 is already preformatted in the workbook. For later rows, inherit
    # the previous decision row's formatting without copying historical values.
    if previous_row >= DECISION_LOG_FIRST_DATA_ROW:
        copy_decision_log_row_format(ws, previous_row, target_row)

    normalized_ticker = str(ticker or "").strip().upper()

    values = [
        date,
        normalized_ticker or None,
        system_view,
        my_view,
        action,
        position_before,
        position_after,
        reason,
        expected_risk,
        review_date,
        result,
    ]

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[DECISION_LOG_SHEET]
    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(DECISION_LOG_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError("Decision_Log post-save verification failed.")

    print("\nDecision_Log append PASS")
    print(f"Workbook : {file_path}")
    print(f"Sheet    : {DECISION_LOG_SHEET}")
    print(f"Row      : {target_row}")
    print(f"Date     : {date}")
    print(f"Ticker   : {normalized_ticker or '<BLANK>'}")
    print(f"Action   : {action}")
    print(f"Result   : {result}")

    return target_row



# ============================================================
# Review_Log writer
# ============================================================

def append_review_log(
    file_path: Path,
    *,
    date,
    ticker,
    review_status,
    review_reason,
    portfolio_flag,
    root_cause_type,
    action_taken,
    resolved,
    resolution_date,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    wb = load_workbook(file_path)

    if REVIEW_LOG_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{REVIEW_LOG_SHEET}' does not exist."
        )

    ws = wb[REVIEW_LOG_SHEET]

    validate_review_log_schema(ws)
    validate_review_log_history_contiguous(ws)
    validate_review_log_duplicate(ws, date, ticker, review_status)
    validate_review_log_values(
        date=date,
        review_status=review_status,
        review_reason=review_reason,
        portfolio_flag=portfolio_flag,
        action_taken=action_taken,
        resolved=resolved,
    )

    target_row = find_first_empty_review_log_row(ws)
    previous_row = target_row - 1

    if previous_row >= REVIEW_LOG_FIRST_DATA_ROW:
        copy_review_log_row_format(ws, previous_row, target_row)

    normalized_ticker = str(ticker or "").strip().upper()

    values = [
        date,
        normalized_ticker or None,
        review_status,
        review_reason,
        portfolio_flag,
        root_cause_type,
        action_taken,
        resolved,
        resolution_date,
    ]

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[REVIEW_LOG_SHEET]
    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(REVIEW_LOG_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError("Review_Log post-save verification failed.")

    print("\nReview_Log append PASS")
    print(f"Workbook     : {file_path}")
    print(f"Sheet        : {REVIEW_LOG_SHEET}")
    print(f"Row          : {target_row}")
    print(f"Date         : {date}")
    print(f"Ticker       : {normalized_ticker or '<BLANK>'}")
    print(f"ReviewStatus : {review_status}")
    print(f"Resolved     : {resolved}")

    return target_row


# ============================================================
# Maintenance_Log writer
# ============================================================

def append_maintenance_log(
    file_path: Path,
    *,
    date,
    category,
    severity,
    ticker_scope,
    issue,
    evidence,
    action=None,
    file_changed=None,
    before=None,
    after=None,
    result=None,
    follow_up_date=None,
    status="OPEN",
    notes=None,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    wb = load_workbook(file_path)

    if MAINTENANCE_LOG_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{MAINTENANCE_LOG_SHEET}' does not exist."
        )

    ws = wb[MAINTENANCE_LOG_SHEET]

    validate_maintenance_log_schema(ws)
    validate_maintenance_log_history_contiguous(ws)
    validate_maintenance_log_duplicate(
        ws,
        date,
        category,
        ticker_scope,
        issue,
    )
    validate_maintenance_log_values(
        date=date,
        category=category,
        severity=severity,
        ticker_scope=ticker_scope,
        issue=issue,
        evidence=evidence,
        status=status,
    )

    target_row = find_first_empty_maintenance_log_row(ws)
    previous_row = target_row - 1

    if previous_row >= MAINTENANCE_LOG_FIRST_DATA_ROW:
        copy_maintenance_log_row_format(ws, previous_row, target_row)

    category_norm = str(category).strip().upper()
    severity_norm = str(severity).strip().upper()
    scope_norm = str(ticker_scope).strip().upper()
    status_norm = str(status).strip().upper()

    values = [
        date,
        category_norm,
        severity_norm,
        scope_norm,
        issue,
        evidence,
        action,
        file_changed,
        before,
        after,
        result,
        follow_up_date,
        status_norm,
        notes,
    ]

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[MAINTENANCE_LOG_SHEET]
    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(MAINTENANCE_LOG_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError("Maintenance_Log post-save verification failed.")

    print("\nMaintenance_Log append PASS")
    print(f"Workbook     : {file_path}")
    print(f"Sheet        : {MAINTENANCE_LOG_SHEET}")
    print(f"Row          : {target_row}")
    print(f"Date         : {date}")
    print(f"Category     : {category_norm}")
    print(f"Severity     : {severity_norm}")
    print(f"Ticker/Scope : {scope_norm}")
    print(f"Status       : {status_norm}")

    return target_row



# ============================================================
# Weekly_Review writer
# ============================================================

def append_weekly_review(
    file_path: Path,
    *,
    week,
    pipeline_reliability,
    data_quality,
    best_candidates,
    review_issues,
    maintenance_summary,
    investment_lessons,
    next_week_focus,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    wb = load_workbook(file_path)

    if WEEKLY_REVIEW_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{WEEKLY_REVIEW_SHEET}' does not exist."
        )

    ws = wb[WEEKLY_REVIEW_SHEET]

    validate_weekly_review_schema(ws)
    validate_weekly_review_history_contiguous(ws)
    validate_weekly_review_duplicate(ws, week)
    validate_weekly_review_values(
        week=week,
        pipeline_reliability=pipeline_reliability,
        data_quality=data_quality,
        best_candidates=best_candidates,
        review_issues=review_issues,
        maintenance_summary=maintenance_summary,
        investment_lessons=investment_lessons,
        next_week_focus=next_week_focus,
    )

    target_row = find_first_empty_weekly_review_row(ws)
    previous_row = target_row - 1

    if previous_row >= WEEKLY_REVIEW_FIRST_DATA_ROW:
        copy_weekly_review_row_format(ws, previous_row, target_row)

    week_norm = _normalize_week_key(week)

    values = [
        week_norm,
        str(pipeline_reliability).strip(),
        str(data_quality).strip(),
        str(best_candidates).strip(),
        str(review_issues).strip(),
        str(maintenance_summary).strip(),
        str(investment_lessons).strip(),
        str(next_week_focus).strip(),
    ]

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[WEEKLY_REVIEW_SHEET]
    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(WEEKLY_REVIEW_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError("Weekly_Review post-save verification failed.")

    print("\nWeekly_Review append PASS")
    print(f"Workbook : {file_path}")
    print(f"Sheet    : {WEEKLY_REVIEW_SHEET}")
    print(f"Row      : {target_row}")
    print(f"Week     : {week_norm}")

    return target_row



# ============================================================
# Monthly_Review writer
# ============================================================

def append_monthly_review(
    file_path: Path,
    *,
    month,
    run_success_rate,
    avg_ready,
    min_ready,
    buy_days,
    watch_days,
    review_count,
    blocked_count,
    top_maintenance_issue,
    system_value,
    main_weakness,
    change_recommended,
) -> int:

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    wb = load_workbook(file_path)

    if MONTHLY_REVIEW_SHEET not in wb.sheetnames:
        raise RuntimeError(
            f"Required sheet '{MONTHLY_REVIEW_SHEET}' does not exist."
        )

    ws = wb[MONTHLY_REVIEW_SHEET]

    validate_monthly_review_schema(ws)
    validate_monthly_review_history_contiguous(ws)
    validate_monthly_review_duplicate(ws, month)
    validate_monthly_review_values(
        month=month,
        run_success_rate=run_success_rate,
        avg_ready=avg_ready,
        min_ready=min_ready,
        buy_days=buy_days,
        watch_days=watch_days,
        review_count=review_count,
        blocked_count=blocked_count,
        top_maintenance_issue=top_maintenance_issue,
        system_value=system_value,
        main_weakness=main_weakness,
        change_recommended=change_recommended,
    )

    target_row = find_first_empty_monthly_review_row(ws)
    previous_row = target_row - 1

    if previous_row >= MONTHLY_REVIEW_FIRST_DATA_ROW:
        copy_monthly_review_row_format(ws, previous_row, target_row)

    month_norm = _normalize_month_key(month)
    change_norm = str(change_recommended).strip().upper()

    values = [
        month_norm,
        str(run_success_rate).strip(),
        avg_ready,
        min_ready,
        buy_days,
        watch_days,
        review_count,
        blocked_count,
        str(top_maintenance_issue).strip(),
        str(system_value).strip(),
        str(main_weakness).strip(),
        change_norm,
    ]

    for col, value in enumerate(values, start=1):
        ws.cell(row=target_row, column=col).value = value

    wb.save(file_path)

    verify_wb = load_workbook(file_path, data_only=False)
    verify_ws = verify_wb[MONTHLY_REVIEW_SHEET]
    verify_values = [
        verify_ws.cell(row=target_row, column=col).value
        for col in range(1, len(MONTHLY_REVIEW_HEADERS) + 1)
    ]

    if verify_values != values:
        raise RuntimeError("Monthly_Review post-save verification failed.")

    print("\nMonthly_Review append PASS")
    print(f"Workbook          : {file_path}")
    print(f"Sheet             : {MONTHLY_REVIEW_SHEET}")
    print(f"Row               : {target_row}")
    print(f"Month             : {month_norm}")
    print(f"RunSuccessRate    : {run_success_rate}")
    print(f"AvgReady          : {avg_ready}")
    print(f"MinReady          : {min_ready}")
    print(f"ChangeRecommended : {change_norm}")

    return target_row


# ============================================================
# Test copy
# ============================================================

def prepare_test_workbook() -> Path:

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Original workbook not found:\n{SOURCE_FILE}"
        )

    shutil.copy2(SOURCE_FILE, TEST_FILE)

    print(f"Test workbook created:\n{TEST_FILE}")

    return TEST_FILE


# ============================================================
# Main test
# ============================================================

if __name__ == "__main__":

    test_file = prepare_test_workbook()

    make_backup(test_file)

    append_daily_run(
        test_file,

        # TEST DATA ONLY
        date=datetime(2099, 1, 1),

        version="TEST",

        pipeline_status="PASS",

        pass_steps=20,

        run_id="TEST-RUN-ID",

        as_of_date=datetime(2098, 12, 31),

        universe_version="TEST-UNIVERSE",

        score_model_version="TEST-SCORE-MODEL",

        risk_model_version="MISSING",

        universe_configured=150,

        ready=148,

        excluded=2,

        provider_rejected=0,

        stale_market_data=0,

        insufficient_history=2,

        excluded_symbols="TEST1, TEST2",

        coverage_status="TEST_ONLY",

        buy=0,

        watch=1,

        ignore=147,

        final_status="NO_ACTION",

        notes="AUTOMATION TEST ROW — SAFE TO DELETE FROM TEST COPY.",
    )

    append_candidate_tracking(
        test_file,
        date=datetime(2099, 1, 1),
        ticker="TESTCAND",
        signal="WATCH",
        rank=1,
        final_score=67.5,
        fundamental_score="MISSING",
        combined_score="MISSING",
        price=123.45,
        why_tracked="CANDIDATE-AUTOMATION-TEST",
        research_note="TEST ONLY — SAFE TO DELETE FROM TEST COPY.",
        day_30=None,
        day_60=None,
        day_90=None,
        outcome="OPEN",
    )

    update_candidate_outcome(
        test_file,
        date=datetime(2099, 1, 1),
        ticker="TESTCAND",
        evaluation_date=datetime(2099, 4, 2),
        day_30=0.10,
        day_60=0.20,
        day_90=0.30,
        outcome="TEST_MATURED",
        create_backup=False,
    )

    append_decision_log(
        test_file,
        date=datetime(2099, 1, 1),
        ticker="TESTCAND",
        system_view="WATCH",
        my_view="WATCH",
        action="NO_ACTION",
        position_before=0,
        position_after=0,
        reason="DECISION-LOG-AUTOMATION-TEST",
        expected_risk="TEST_ONLY",
        review_date=datetime(2099, 4, 2),
        result="OPEN",
    )

    append_review_log(
        test_file,
        date=datetime(2099, 1, 1),
        ticker="TESTCAND",
        review_status="REVIEW",
        review_reason="REVIEW-LOG-AUTOMATION-TEST",
        portfolio_flag="TEST_ONLY",
        root_cause_type="TEST",
        action_taken="NO_ACTION",
        resolved=False,
        resolution_date=None,
    )


    append_maintenance_log(
        test_file,
        date=datetime(2099, 1, 1),
        category="CODE_BUG",
        severity="P3",
        ticker_scope="ALL",
        issue="MAINTENANCE-LOG-AUTOMATION-TEST",
        evidence="TEST ONLY — SAFE TO DELETE FROM TEST COPY.",
        action="NO_CHANGE_OBSERVE",
        file_changed=None,
        before="TEST_BEFORE",
        after="TEST_AFTER",
        result="NO_CHANGE",
        follow_up_date=datetime(2099, 2, 1),
        status="MONITORING",
        notes="AUTOMATION TEST ROW — SAFE TO DELETE FROM TEST COPY.",
    )

    append_weekly_review(
        test_file,
        week="2098-12-28 to 2099-01-03",
        pipeline_reliability="WEEKLY-REVIEW-AUTOMATION-TEST: pipeline reliability PASS.",
        data_quality="TEST_ONLY — data quality summary.",
        best_candidates="TESTCAND remained the test candidate.",
        review_issues="TEST_ONLY — no production inference.",
        maintenance_summary="TEST_ONLY — maintenance summary.",
        investment_lessons="TEST_ONLY — investment lessons.",
        next_week_focus="TEST ONLY — SAFE TO DELETE FROM TEST COPY.",
    )


    append_monthly_review(
        test_file,
        month="2099-01",
        run_success_rate="100% (TEST)",
        avg_ready=148.0,
        min_ready=147,
        buy_days=0,
        watch_days=1,
        review_count=1,
        blocked_count=0,
        top_maintenance_issue="TEST_ONLY — monthly maintenance issue summary.",
        system_value="TEST_ONLY — monthly system value summary.",
        main_weakness="TEST_ONLY — monthly main weakness summary.",
        change_recommended="OBSERVE",
    )

