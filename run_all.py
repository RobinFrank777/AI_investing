import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from backtest_engine import backtest_watchlist
from combined_scoring import print_combined_score
from current_run_status import finish_current_run, start_current_run
from config import (
    BACKTEST_ALL_TRADES_20D_OUTPUT_PATH,
    BACKTEST_QUALIFIED_20D_OUTPUT_PATH,
    BACKTEST_SUMMARY_20D_OUTPUT_PATH,
    COMBINED_SCORE_OUTPUT_PATH,
    DAILY_DECISION_REPORT_PREFIX_PATH,
    FUNDAMENTAL_SCORE_OUTPUT_PATH,
    LOGS_DIR_PATH,
    MODEL_PORTFOLIO_OUTPUT_PATH,
    ORDER_DRAFT_OUTPUT_PATH,
    ORDER_REVIEW_OUTPUT_PATH,
    PORTFOLIO_ACTION_REPORT_OUTPUT_PATH,
    POSITION_SIZING_OUTPUT_PATH,
    PROJECT_VERSION,
    REPO_ROOT,
    STOCK_RANK_OUTPUT_PATH,
    TOP10_OUTPUT_PATH,
    display_path,
)
from daily_decision_report import print_daily_decision_report
from data_readiness import build_data_readiness
from data_validator import print_validation_summary, validate_watchlist
from fundamental_scoring import print_fundamental_score
from order_draft import print_order_draft
from order_review import print_order_review
from portfolio_action_report import print_portfolio_action_report
from production_candidate_builder import (
    DEFAULT_OUTPUT_PATH as PRODUCTION_CANDIDATE_OUTPUT_PATH,
    run_production_candidate_builder,
)
from portfolio_risk import print_model_portfolio
from position_sizing import print_position_sizing
from rank_stocks_v2 import run_ranking_pipeline
from system_health_check import get_manual_input_readiness, run_system_health_check
from update_data import load_watchlist, update_all_stocks
from validate_backtest_outputs import validate_backtest_outputs
from validate_combined_outputs import validate_combined_outputs
from validate_config import print_config_validation
from validate_daily_decision_report_outputs import validate_daily_decision_report_outputs
from validate_fundamental_outputs import validate_fundamental_outputs
from validate_order_draft_outputs import validate_order_draft_outputs
from validate_order_review_outputs import validate_order_review_outputs
from validate_portfolio_outputs import validate_portfolio_outputs
from validate_position_sizing_outputs import validate_position_sizing_outputs


DISCLAIMER_LINES = (
    "This system provides research outputs only.",
    "Validation PASS is not investment approval.",
    "All investment decisions require independent human review.",
    "No brokerage order was submitted.",
)


class SanitizedTee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, message):
        safe_message = sanitize_text(message)
        for stream in self.streams:
            stream.write(safe_message)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def sanitize_text(value):
    safe_text = str(value).replace(str(REPO_ROOT), ".")
    return safe_text.replace(str(Path.home()), "$HOME")


def get_git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "UNKNOWN"


def artifact_state(path):
    if not path.is_file():
        return False, None, None

    stat_result = path.stat()
    return True, stat_result.st_mtime_ns, stat_result.st_size


def verify_artifacts_updated(before_states, artifacts):
    for artifact in artifacts:
        after_state = artifact_state(artifact)

        if not after_state[0]:
            raise FileNotFoundError(
                f"Expected artifact was not produced: {display_path(artifact)}"
            )

        if after_state[2] == 0:
            raise RuntimeError(
                f"Expected artifact is empty: {display_path(artifact)}"
            )

        if after_state == before_states[artifact]:
            raise RuntimeError(
                f"Expected artifact was not updated: {display_path(artifact)}"
            )


def run_step(step):
    started_at = datetime.now()
    started_clock = time.monotonic()
    artifacts = ()

    print("\n" + "=" * 80)
    print(f"STEP START: {step['name']}")
    print(f"Started At: {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    try:
        configured_artifacts = step.get("artifacts", ())
        if callable(configured_artifacts):
            configured_artifacts = configured_artifacts()
        artifacts = tuple(configured_artifacts)
        before_states = {path: artifact_state(path) for path in artifacts}

        step["action"]()

        if artifacts:
            verify_artifacts_updated(before_states, artifacts)

        validator = step.get("validator")
        if validator is not None:
            validator()

    except Exception as error:
        elapsed = time.monotonic() - started_clock
        print(f"STEP STATUS: FAIL")
        print(f"Elapsed: {elapsed:.3f}s")
        print(f"Exception: {type(error).__name__}")
        print(f"Error: {sanitize_text(error)}")
        print("Traceback:")
        print(sanitize_text(traceback.format_exc()))

        return {
            "name": step["name"],
            "status": "FAIL",
            "elapsed": elapsed,
            "artifacts": artifacts,
            "exception": type(error).__name__,
            "error": sanitize_text(error),
        }

    elapsed = time.monotonic() - started_clock
    print("STEP STATUS: PASS")
    print(f"Elapsed: {elapsed:.3f}s")
    for artifact in artifacts:
        print(f"Artifact: {display_path(artifact)}")

    return {
        "name": step["name"],
        "status": "PASS",
        "elapsed": elapsed,
        "artifacts": artifacts,
        "exception": "",
        "error": "",
    }


def execute_steps(steps):
    results = []
    failed = False

    for step in steps:
        if failed:
            results.append(
                {
                    "name": step["name"],
                    "status": "SKIP",
                    "elapsed": 0.0,
                    "artifacts": (),
                    "exception": "",
                    "error": "Blocked by an earlier required-step failure.",
                }
            )
            continue

        result = run_step(step)
        results.append(result)

        if result["status"] == "FAIL" and step.get("required", True):
            failed = True

    return results


def preflight():
    if not REPO_ROOT.is_dir():
        raise RuntimeError("Repository root is unavailable.")


def validate_manual_inputs():
    readiness = get_manual_input_readiness()
    missing_inputs = [path for path, state in readiness.items() if not state["ready"]]

    if missing_inputs:
        missing_display = ", ".join(display_path(path) for path in missing_inputs)
        raise FileNotFoundError(f"Missing required manual input: {missing_display}")

    print("Required manual inputs are ready:")
    for path in readiness:
        print(f"- {display_path(path)}")


def validate_market_data():
    results, universe_latest_date = validate_watchlist()
    print_validation_summary(results, universe_latest_date)

    readiness_exclusions = []
    fatal_tickers = []
    for result in results:
        if result["IsValid"]:
            if result.get("Warnings"):
                fatal_tickers.append(result["Ticker"])
            continue
        errors = result.get("Errors", [])
        if errors and all(
            str(error).startswith("Insufficient history:") for error in errors
        ):
            readiness_exclusions.append(result["Ticker"])
        else:
            fatal_tickers.append(result["Ticker"])

    if fatal_tickers:
        raise RuntimeError(
            "Market data validation failed for: " + ", ".join(fatal_tickers)
        )
    if readiness_exclusions:
        print(
            "Market data readiness exclusions (insufficient history; "
            "Universe membership unchanged): " + ", ".join(readiness_exclusions)
        )

    readiness = build_data_readiness()
    readiness_failures = readiness.loc[
        (~readiness["Ready"])
        & (~readiness["Reason"].eq("INSUFFICIENT_HISTORY"))
    ]
    if not readiness_failures.empty:
        details = ", ".join(
            f"{row.Ticker} ({row.Reason})"
            for row in readiness_failures.itertuples(index=False)
        )
        raise RuntimeError("Market data readiness failed for: " + details)


def market_data_artifacts():
    from config import DATA_DIR_PATH

    return tuple(DATA_DIR_PATH / f"{ticker}.csv" for ticker in load_watchlist())


def update_market_data():
    """Attempt refresh; the following validator decides data usability."""
    result = update_all_stocks()
    print(
        "Market data update attempts: "
        f"{result['succeeded']} succeeded, {result['failed']} failed"
    )
    if result["failed_symbols"]:
        print(
            "Refresh failures pending validation of existing local data: "
            + ", ".join(result["failed_symbols"])
        )
    return result


def daily_report_path():
    report_date = datetime.now().strftime("%Y-%m-%d")
    return REPO_ROOT / f"reports/daily_trading_report_{report_date}.txt"


def daily_decision_report_path():
    report_date = datetime.now().strftime("%Y-%m-%d")
    return DAILY_DECISION_REPORT_PREFIX_PATH.parent / (
        f"{DAILY_DECISION_REPORT_PREFIX_PATH.name}_{report_date}.txt"
    )


def build_pipeline_steps():
    return [
        {"name": "Preflight", "action": preflight},
        {"name": "Config validation", "action": print_config_validation},
        {"name": "Repository health", "action": run_system_health_check},
        {"name": "Manual input readiness", "action": validate_manual_inputs},
        {
            "name": "Market data update",
            "action": update_market_data,
        },
        {"name": "Market data validation", "action": validate_market_data},
        {
            "name": "Daily screening",
            "action": run_ranking_pipeline,
            "artifacts": (
                STOCK_RANK_OUTPUT_PATH,
                TOP10_OUTPUT_PATH,
                daily_report_path(),
            ),
        },
        {
            "name": "20 day backtest",
            "action": lambda: backtest_watchlist(holding_days=20),
            "artifacts": (
                BACKTEST_SUMMARY_20D_OUTPUT_PATH,
                BACKTEST_QUALIFIED_20D_OUTPUT_PATH,
                BACKTEST_ALL_TRADES_20D_OUTPUT_PATH,
            ),
        },
        {"name": "Backtest validation", "action": validate_backtest_outputs},
        {
            "name": "Production candidate build",
            "action": run_production_candidate_builder,
            "artifacts": (PRODUCTION_CANDIDATE_OUTPUT_PATH,),
        },
        {
            "name": "Model portfolio",
            "action": print_model_portfolio,
            "artifacts": (MODEL_PORTFOLIO_OUTPUT_PATH,),
            "validator": validate_portfolio_outputs,
        },
        {
            "name": "Fundamental scoring",
            "action": print_fundamental_score,
            "artifacts": (FUNDAMENTAL_SCORE_OUTPUT_PATH,),
            "validator": validate_fundamental_outputs,
        },
        {
            "name": "Combined scoring",
            "action": print_combined_score,
            "artifacts": (COMBINED_SCORE_OUTPUT_PATH,),
            "validator": validate_combined_outputs,
        },
        {
            "name": "Position sizing",
            "action": print_position_sizing,
            "artifacts": (POSITION_SIZING_OUTPUT_PATH,),
            "validator": validate_position_sizing_outputs,
        },
        {
            "name": "Order draft",
            "action": print_order_draft,
            "artifacts": (ORDER_DRAFT_OUTPUT_PATH,),
            "validator": validate_order_draft_outputs,
        },
        {
            "name": "Order review",
            "action": print_order_review,
            "artifacts": (ORDER_REVIEW_OUTPUT_PATH,),
            "validator": validate_order_review_outputs,
        },
        {
            "name": "Portfolio action report",
            "action": print_portfolio_action_report,
            "artifacts": (PORTFOLIO_ACTION_REPORT_OUTPUT_PATH,),
        },
        {
            "name": "Daily decision report",
            "action": print_daily_decision_report,
            "artifacts": (daily_decision_report_path(),),
        },
        {
            "name": "Final validation",
            "action": validate_daily_decision_report_outputs,
        },
    ]


def print_summary(results, started_at, finished_at):
    status = "PASS" if all(result["status"] == "PASS" for result in results) else "FAIL"
    elapsed = (finished_at - started_at).total_seconds()

    print("\n" + "=" * 80)
    print(f"AI_investing {PROJECT_VERSION} Pipeline Summary")
    print("=" * 80)
    print(f"Status      : {status}")
    print(f"Started At  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Finished At : {finished_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed     : {elapsed:.3f}s")
    print(f"Version     : {PROJECT_VERSION}")
    print(f"Git Commit  : {get_git_commit()}")
    print("\nSteps:")

    for index, result in enumerate(results, start=1):
        print(f"{index:>2}. {result['name']:<30} {result['status']}")
        if result["error"]:
            print(f"    {result['error']}")
        for artifact in result["artifacts"]:
            if artifact.is_file():
                print(f"    - {display_path(artifact)}")

    print("")
    for line in DISCLAIMER_LINES:
        print(line)

    return status


def _successful_candidate_identity():
    try:
        import pandas as pd

        frame = pd.read_csv(PRODUCTION_CANDIDATE_OUTPUT_PATH)
        if frame.empty:
            return None, None
        run_ids = frame["RunId"].dropna().astype(str).str.strip().unique()
        as_of_dates = frame["AsOfDate"].dropna().astype(str).str.strip().unique()
        if len(run_ids) == 1 and len(as_of_dates) == 1:
            return run_ids[0], as_of_dates[0]
    except (KeyError, OSError, UnicodeError, pd.errors.ParserError):
        pass
    return None, None


def write_failed_current_reports(context):
    """Make current report paths explicitly represent the latest failed run."""
    failed_stage = context.get("FailedStage") or "UNKNOWN"
    reason = context.get("FailureReason") or "Required pipeline stage failed"
    run_id = context.get("CurrentRunId") or "MISSING"
    as_of_date = context.get("AsOfDate") or "MISSING"
    failure = (
        "Report Status          : FAILED\n"
        f"RunId                 : {run_id}\n"
        f"AsOfDate              : {as_of_date}\n"
        f"Failed Stage          : {failed_stage}\n"
        f"Failure Reason        : {reason}\n"
        "Prior artifacts are historical and are not current production evidence.\n"
        "No brokerage order was submitted.\n"
    )
    PORTFOLIO_ACTION_REPORT_OUTPUT_PATH.write_text(failure, encoding="utf-8")
    decision_path = daily_decision_report_path()
    decision_path.write_text(
        "AI INVESTING DAILY DECISION REPORT\n"
        "Report Context: LATEST PIPELINE ATTEMPT FAILED\n\n"
        "PART 1 - RESEARCH_ONLY DAILY TECHNICAL SCREENING REPORT\n"
        "Not produced for the failed latest attempt.\n\n"
        "PART 2 - EVIDENCE-VALIDATED PORTFOLIO ACTION REPORT\n"
        + failure
        + "\nFINAL REMINDER\nAll trades must be reviewed before execution.\n",
        encoding="utf-8",
    )


def run_pipeline(steps=None):
    context = start_current_run()
    started_at = datetime.now()
    steps = build_pipeline_steps() if steps is None else steps
    results = execute_steps(steps)
    finished_at = datetime.now()
    status = print_summary(results, started_at, finished_at)
    if status == "PASS":
        candidate_run_id, candidate_as_of = _successful_candidate_identity()
        finish_current_run(
            context, status="PASS", current_run_id=candidate_run_id,
            as_of_date=candidate_as_of,
        )
    else:
        failed = next(
            (result for result in results if result["status"] == "FAIL"), None
        )
        context = finish_current_run(
            context,
            status="FAILED",
            failed_stage=failed["name"] if failed else "UNKNOWN",
            reason=failed["error"] if failed else "Required pipeline stage failed",
        )
        write_failed_current_reports(context)
    return 0 if status == "PASS" else 1


def main():
    LOGS_DIR_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = LOGS_DIR_PATH / f"all_pipeline_{timestamp}.log"
    original_stdout = sys.stdout

    with log_path.open("w", encoding="utf-8") as log_file:
        sys.stdout = SanitizedTee(original_stdout, log_file)
        try:
            print(f"AI_investing {PROJECT_VERSION} One Command Pipeline")
            print(f"Git Commit: {get_git_commit()}")
            print(f"Log File: {display_path(log_path)}")
            return run_pipeline()
        finally:
            sys.stdout = original_stdout


if __name__ == "__main__":
    sys.exit(main())
