import subprocess
import sys
from datetime import datetime


def run_command(command):
    print("\n" + "=" * 70)
    print(f"Running: {' '.join(command)}")
    print("=" * 70)

    subprocess.run(
        command,
        check=True,
    )


def main():
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 70)
    print("AI INVESTING DAILY PIPELINE")
    print("=" * 70)
    print(f"Started At: {started_at}")

    run_command(
        [
            sys.executable,
            "update_data.py",
        ]
    )

    run_command(
        [
            sys.executable,
            "rank_stocks_v2.py",
        ]
    )

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 70)
    print("DAILY PIPELINE COMPLETED")
    print("=" * 70)
    print(f"Finished At: {finished_at}")


if __name__ == "__main__":
    main()