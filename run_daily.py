import sys
import traceback
from datetime import datetime

from rank_stocks_v2 import run_ranking_pipeline
from update_data import update_all_stocks


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run_step(step_name, step_function):
    print_section(f"Running: {step_name}")

    try:
        step_function()

    except Exception as error:
        print_section(f"FAILED: {step_name}")
        print(f"Error Type: {type(error).__name__}")
        print(f"Error Message: {error}")
        print("\nFull traceback:")
        traceback.print_exc()
        raise

    print_section(f"Completed: {step_name}")


def main():
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("AI INVESTING DAILY PIPELINE")
    print(f"Started At: {started_at}")

    try:
        run_step(
            "Update market data",
            update_all_stocks,
        )

        run_step(
            "Generate ranking and daily report",
            run_ranking_pipeline,
        )

    except Exception:
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print_section("DAILY PIPELINE FAILED")
        print(f"Finished At: {finished_at}")

        sys.exit(1)

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("DAILY PIPELINE COMPLETED")
    print(f"Finished At: {finished_at}")


if __name__ == "__main__":
    main()