from datetime import datetime

from portfolio_risk import print_model_portfolio


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("AI INVESTING PORTFOLIO PIPELINE")
    print(f"Started At: {started_at}")

    print_section("Running: Build model portfolio")
    print_model_portfolio()
    print_section("Completed: Build model portfolio")

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_section("PORTFOLIO PIPELINE COMPLETED")
    print(f"Finished At: {finished_at}")


if __name__ == "__main__":
    main()