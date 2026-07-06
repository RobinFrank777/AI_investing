import sys
from datetime import datetime
from pathlib import Path

from portfolio_risk import print_model_portfolio
from validate_portfolio_outputs import validate_portfolio_outputs
from position_sizing import print_position_sizing
from validate_position_sizing_outputs import validate_position_sizing_outputs
from order_draft import print_order_draft
from validate_order_draft_outputs import validate_order_draft_outputs
from order_review import print_order_review
from validate_order_review_outputs import validate_order_review_outputs
from portfolio_action_report import print_portfolio_action_report

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

    print_section("Running: Position sizing")
    print_position_sizing()
    print_section("Completed: Position sizing")

    print_section("Running: Validate position sizing outputs")
    validate_position_sizing_outputs()
    print_section("Completed: Validate position sizing outputs")

    print_section("Running: Generate order draft")
    print_order_draft()
    print_section("Completed: Generate order draft")

    print_section("Running: Validate order draft outputs")
    validate_order_draft_outputs()
    print_section("Completed: Validate order draft outputs")

    print_section("Running: Review order draft")
    print_order_review()
    print_section("Completed: Review order draft")

    print_section("Running: Validate order review outputs")
    validate_order_review_outputs()
    print_section("Completed: Validate order review outputs")

    print_section("Running: Generate portfolio action report")
    print_portfolio_action_report()
    print_section("Completed: Generate portfolio action report")

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("PORTFOLIO PIPELINE COMPLETED")
    print(f"Finished At: {finished_at}")


if __name__ == "__main__":
    main()