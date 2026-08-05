import csv
from pathlib import Path

from stock_card_report import generate_stock_card_report


PROJECT_ROOT = Path(__file__).resolve().parent
TOP10_PATH = PROJECT_ROOT / "results" / "top10.csv"
MODEL_PORTFOLIO_PATH = PROJECT_ROOT / "results" / "model_portfolio.csv"
CARDS_DIR = PROJECT_ROOT / "reports" / "cards"


def _normalized_symbol(value):
    symbol = str(value).strip().upper() if value is not None else ""
    return "" if symbol in {"", "NAN"} else symbol


def _read_symbols(csv_path, source_name, required):
    if not csv_path.exists():
        if required:
            raise FileNotFoundError(f"{source_name} CSV not found: {csv_path}")
        print(f"Warning: {source_name} CSV not found; continuing without it.")
        return []

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or "Ticker" not in reader.fieldnames:
            if required:
                raise ValueError(f"{source_name} CSV must contain a Ticker column.")
            print(
                f"Warning: {source_name} CSV has no Ticker column; "
                "continuing without it."
            )
            return []
        return [
            symbol
            for row in reader
            if (symbol := _normalized_symbol(row.get("Ticker")))
        ]


def generate_all_stock_cards():
    top10_symbols = _read_symbols(TOP10_PATH, "Top10", required=True)
    portfolio_symbols = _read_symbols(
        MODEL_PORTFOLIO_PATH,
        "Model Portfolio",
        required=False,
    )

    symbols = []
    seen = set()
    for symbol in top10_symbols + portfolio_symbols:
        if symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)

    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    return [generate_stock_card_report(symbol) for symbol in symbols]


def main():
    generated_paths = generate_all_stock_cards()
    print(f"Generated stock cards: {len(generated_paths)}")
    for path in generated_paths:
        print(path.name)


if __name__ == "__main__":
    main()
