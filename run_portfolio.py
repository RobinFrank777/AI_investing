import sys
from datetime import datetime
from pathlib import Path

from portfolio_risk import print_model_portfolio
from validate_portfolio_outputs import validate_portfolio_outputs

LOG_DIR = Path("logs")


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, message):
        for stream in self.streams:
            stream.write(message)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)

    log_date = datetime.now().strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"portfolio_pipeline_{log_date}.log"

    log_file = open(log_path, "w", encoding="utf-8")

    sys.stdout = Tee(sys.stdout, log_file)

    return log_path

def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    log_path = setup_logging()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("AI INVESTING PORTFOLIO PIPELINE")
    print(f"Started At: {started_at}")
    print(f"Log File: {log_path}")

    print_section("Running: Build model portfolio")
    print_model_portfolio()
    print_section("Completed: Build model portfolio")

    print_section("Running: Validate portfolio outputs")
    validate_portfolio_outputs()
    print_section("Completed: Validate portfolio outputs")

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("PORTFOLIO PIPELINE COMPLETED")
    print(f"Finished At: {finished_at}")


if __name__ == "__main__":
    main()