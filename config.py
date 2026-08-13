"""
Central configuration for AI_investing.

This file stores shared system parameters used by ranking, portfolio sizing,
order draft, order review, reporting, and future risk-control modules.

Older variable names are kept for backward compatibility.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


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
# Scoring settings
# ============================================================

BACKTEST_SCORE_WEIGHT = 0.7
FUNDAMENTAL_SCORE_WEIGHT = 0.3

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
ALLOWED_PORTFOLIO_REVIEW_FLAG = [
    "PASS",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "NOT_APPLICABLE",
]

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
PROJECT_VERSION = "v3.8.0"
STOCK_RANK_OUTPUT = "results/stock_rank.csv"
TOP10_OUTPUT = "results/top10.csv"

MODEL_PORTFOLIO_OUTPUT = "results/model_portfolio.csv"
POSITION_SIZING_OUTPUT = "results/model_portfolio_sizing.csv"
ORDER_DRAFT_OUTPUT = "results/order_draft.csv"
ORDER_REVIEW_OUTPUT = "results/order_review.csv"

PORTFOLIO_ACTION_REPORT_OUTPUT = "results/portfolio_action_report.txt"
SYSTEM_VERSION_OUTPUT = "results/system_version.txt"
DAILY_DECISION_REPORT_PREFIX = "reports/daily_decision_report"

FUNDAMENTAL_INPUT = "data/fundamentals.csv"
FUNDAMENTAL_SCORE_OUTPUT = "results/fundamental_score.csv"
COMBINED_SCORE_OUTPUT = "results/combined_score.csv"


# ============================================================
# Repository-root anchored paths
# ============================================================

# The string constants above remain available for backward compatibility and
# human-readable output. Filesystem operations should use these Path constants.
DATA_DIR_PATH = REPO_ROOT / DATA_DIR
RESULTS_DIR_PATH = REPO_ROOT / RESULTS_DIR
REPORTS_DIR_PATH = REPO_ROOT / REPORTS_DIR
LOGS_DIR_PATH = REPO_ROOT / LOGS_DIR

WATCHLIST_INPUT_PATH = DATA_DIR_PATH / "watchlist.csv"
WATCHLIST_EXAMPLE_PATH = DATA_DIR_PATH / "watchlist.example.csv"
# The sole authority for the production investment universe.  watchlist.csv is
# retained below for legacy and compatibility workflows only.
PRIMARY_UNIVERSE_PATH = DATA_DIR_PATH / "AI_investing_universe_150_V2.csv"
PRIMARY_UNIVERSE_VERSION = "AI_investing_universe_150_V2"
UNIVERSE_MODE = "single"
UNIVERSE_CONFIG_PATH = DATA_DIR_PATH / "universe_config.csv"
FUNDAMENTALS_EXAMPLE_PATH = DATA_DIR_PATH / "fundamentals.example.csv"

STOCK_RANK_OUTPUT_PATH = REPO_ROOT / STOCK_RANK_OUTPUT
TOP10_OUTPUT_PATH = REPO_ROOT / TOP10_OUTPUT
MODEL_PORTFOLIO_OUTPUT_PATH = REPO_ROOT / MODEL_PORTFOLIO_OUTPUT
POSITION_SIZING_OUTPUT_PATH = REPO_ROOT / POSITION_SIZING_OUTPUT
ORDER_DRAFT_OUTPUT_PATH = REPO_ROOT / ORDER_DRAFT_OUTPUT
ORDER_REVIEW_OUTPUT_PATH = REPO_ROOT / ORDER_REVIEW_OUTPUT
PORTFOLIO_ACTION_REPORT_OUTPUT_PATH = REPO_ROOT / PORTFOLIO_ACTION_REPORT_OUTPUT
SYSTEM_VERSION_OUTPUT_PATH = REPO_ROOT / SYSTEM_VERSION_OUTPUT
DAILY_DECISION_REPORT_PREFIX_PATH = REPO_ROOT / DAILY_DECISION_REPORT_PREFIX
FUNDAMENTAL_INPUT_PATH = REPO_ROOT / FUNDAMENTAL_INPUT
FUNDAMENTAL_SCORE_OUTPUT_PATH = REPO_ROOT / FUNDAMENTAL_SCORE_OUTPUT
COMBINED_SCORE_OUTPUT_PATH = REPO_ROOT / COMBINED_SCORE_OUTPUT

BACKTEST_SUMMARY_20D_OUTPUT_PATH = RESULTS_DIR_PATH / "backtest_summary_20d.csv"
BACKTEST_QUALIFIED_20D_OUTPUT_PATH = RESULTS_DIR_PATH / "backtest_qualified_20d.csv"
BACKTEST_ALL_TRADES_20D_OUTPUT_PATH = RESULTS_DIR_PATH / "backtest_all_trades_20d.csv"


def display_path(path):
    """Return a repository-relative path for user-visible output."""
    path = Path(path)

    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
