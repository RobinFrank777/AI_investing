from datetime import datetime
from pathlib import Path
import sys
import traceback

from rank_stocks_v2 import run_ranking_pipeline
from update_data import update_all_stocks


LOG_DIR = Path("logs")


def get_log_file():
    today = datetime.now().strftime("%Y-%m-%d")
    LOG_DIR.mkdir(exist_ok=True)

    return LOG_DIR / f"daily_pipeline_{today}.log"


def write_log(message, log_file):
    print(message)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def print_section(title, log_file):
    write_log("\n" + "=" * 70, log_file)
    write_log(title, log_file)
    write_log("=" * 70, log_file)


def run_step(step_name, step_function, log_file):
    print_section(f"Running: {step_name}", log_file)

    try:
        step_function()

    except Exception as error:
        print_section(f"FAILED: {step_name}", log_file)
        write_log(f"Error Type: {type(error).__name__}", log_file)
        write_log(f"Error Message: {error}", log_file)
        write_log("", log_file)
        write_log("Full traceback:", log_file)

        traceback_text = traceback.format_exc()
        write_log(traceback_text, log_file)

        raise

    print_section(f"Completed: {step_name}", log_file)


def main():
    log_file = get_log_file()

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("AI INVESTING DAILY PIPELINE", log_file)
    write_log(f"Started At: {started_at}", log_file)
    write_log(f"Log File: {log_file}", log_file)

    try:
        run_step(
            "Update market data",
            update_all_stocks,
            log_file,
        )

        run_step(
            "Generate ranking and daily report",
            run_ranking_pipeline,
            log_file,
        )

    except Exception:
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print_section("DAILY PIPELINE FAILED", log_file)
        write_log(f"Finished At: {finished_at}", log_file)

        sys.exit(1)

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("DAILY PIPELINE COMPLETED", log_file)
    write_log(f"Finished At: {finished_at}", log_file)


if __name__ == "__main__":
    main()