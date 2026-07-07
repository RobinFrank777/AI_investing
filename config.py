"""
Central configuration for AI_investing.

This file stores shared system parameters used by ranking, portfolio sizing,
order draft, order review, reporting, and future risk-control modules.

Older variable names are kept for backward compatibility.
"""


# ============================================================
# Account settings
# ============================================================

ACCOUNT_VALUE = 100_000

# Backward compatibility with earlier modules
ACCOUNT_SIZE = ACCOUNT_VALUE


# ============================================================
# Position risk settings
# ============================================================

RISK_PER_TRADE = 0.01


# ============================================================
# Portfolio risk settings
# ============================================================

MAX_HOLDINGS = 10
MAX_SINGLE_POSITION_WEIGHT = 0.10
MAX_TOTAL_EXPOSURE = 0.80
CASH_RESERVE_RATIO = 0.20


# ============================================================
# Risk weight multipliers
# ============================================================

LOW_RISK_WEIGHT_MULTIPLIER = 1.00
MEDIUM_RISK_WEIGHT_MULTIPLIER = 0.80
HIGH_RISK_WEIGHT_MULTIPLIER = 0.50
UNKNOWN_RISK_WEIGHT_MULTIPLIER = 0.00


# ============================================================
# Order review settings
# ============================================================

MAX_ORDER_COUNT = 10
MAX_TOTAL_ORDER_VALUE = 80_000
MAX_SINGLE_ORDER_VALUE = 10_000

ALLOWED_ACTIONS = ["BUY"]
ALLOWED_ORDER_STATUS = ["DRAFT_ONLY"]
ALLOWED_REVIEW_STATUS = ["PASS", "REVIEW", "BLOCKED"]
ALLOWED_PORTFOLIO_REVIEW_FLAG = ["PASS", "REVIEW"]


# ============================================================
# Output directories
# ============================================================

DATA_DIR = "data"
RESULTS_DIR = "results"
REPORTS_DIR = "reports"
LOGS_DIR = "logs"


# ============================================================
# Output files
# ============================================================

STOCK_RANK_OUTPUT = "results/stock_rank.csv"
TOP10_OUTPUT = "results/top10.csv"

MODEL_PORTFOLIO_OUTPUT = "results/model_portfolio.csv"
POSITION_SIZING_OUTPUT = "results/model_portfolio_sizing.csv"
ORDER_DRAFT_OUTPUT = "results/order_draft.csv"
ORDER_REVIEW_OUTPUT = "results/order_review.csv"

PORTFOLIO_ACTION_REPORT_OUTPUT = "results/portfolio_action_report.txt"
SYSTEM_VERSION_OUTPUT = "results/system_version.txt"
DAILY_DECISION_REPORT_PREFIX = "reports/daily_decision_report"