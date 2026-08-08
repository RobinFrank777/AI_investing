"""Command-line entry point for the daily research pipeline."""

import argparse
import sys
from pathlib import Path

import daily_research_pipeline
import research_pipeline_logger


PROJECT_ROOT = Path(__file__).resolve().parent
DISPLAY_STEPS = (
    "Factor Preparation",
    "Ranking",
    "Research Report",
    "Signal Generation",
    "Risk Analysis",
    "Risk Factor Merge",
    "Dataset Validation",
    "Candidate Selection",
    "Candidate Report",
    "Daily Snapshot",
    "Research Explanation",
    "AI Research Summary",
    "Report Composer",
)


def _parser():
    parser = argparse.ArgumentParser(description="Run the daily research pipeline.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the fixed pipeline sequence without running it",
    )
    return parser


def _display_path(value):
    path = Path(value)
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _print_sequence():
    print("Daily Research Pipeline")
    print()
    for number, step_name in enumerate(DISPLAY_STEPS, start=1):
        print(f"{number}. {step_name}")


def _print_summary(result):
    status = result["status"]
    counts = status["Status"].value_counts().to_dict()
    print("Daily Research Pipeline Completed")
    print()
    print("PASS:")
    print(int(counts.get("PASS", 0)))
    print()
    print("FAILED:")
    print(int(counts.get("FAILED", 0)))
    print()
    print("SKIPPED:")
    print(int(counts.get("SKIPPED", 0)))
    print()
    print("Report:")
    print(_display_path(result["output_path"]))
    run_date = status["RunDate"].iloc[0] if not status.empty else None
    print()
    print("Log:")
    print(_display_path(research_pipeline_logger.pipeline_log_path(run_date)))
    return 1 if counts.get("FAILED", 0) else 0


def main(argv=None):
    """Parse CLI arguments and invoke the single pipeline entry point."""
    arguments = _parser().parse_args(argv)
    if arguments.dry_run:
        _print_sequence()
        return 0
    try:
        result = daily_research_pipeline.run_daily_research_pipeline()
        return _print_summary(result)
    except Exception as error:  # CLI boundary hides implementation tracebacks.
        message = str(error).strip() or error.__class__.__name__
        print(f"Daily Research Pipeline failed: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
