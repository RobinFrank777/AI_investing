import csv
from pathlib import Path

from stock_card_report import generate_stock_card_report


PROJECT_ROOT = Path(__file__).resolve().parent
TOP10_PATH = PROJECT_ROOT / "results" / "top10.csv"
CARDS_DIR = PROJECT_ROOT / "reports" / "cards"


def generate_all_stock_cards():
    if not TOP10_PATH.exists():
        raise FileNotFoundError(f"Top10 CSV not found: {TOP10_PATH}")

    with TOP10_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or "Ticker" not in reader.fieldnames:
            raise ValueError("Top10 CSV must contain a Ticker column.")
        symbols = [
            row["Ticker"].strip().upper()
            for row in reader
            if row.get("Ticker") and row["Ticker"].strip()
        ]

    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    return [generate_stock_card_report(symbol) for symbol in symbols]


def main():
    generated_paths = generate_all_stock_cards()
    print("Generated stock cards:")
    for path in generated_paths:
        print(path.name)


if __name__ == "__main__":
    main()
