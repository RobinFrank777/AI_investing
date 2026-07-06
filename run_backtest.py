from datetime import datetime

from backtest_engine import backtest_watchlist
from validate_backtest_outputs import validate_backtest_outputs


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("AI INVESTING BACKTEST PIPELINE")
    print(f"Started At: {started_at}")

    print_section("Running: Batch backtest")
    backtest_watchlist(holding_days=20)
    print_section("Completed: Batch backtest")

    print_section("Running: Validate backtest outputs")
    validate_backtest_outputs()
    print_section("Completed: Validate backtest outputs")

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("BACKTEST PIPELINE COMPLETED")
    print(f"Finished At: {finished_at}")


if __name__ == "__main__":
    main()