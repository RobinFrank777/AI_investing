from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"

CARD_SOURCES = {
    "top_opportunity": RESULTS_DIR / "top10.csv",
    "model_portfolio": RESULTS_DIR / "model_portfolio.csv",
    "order_review": RESULTS_DIR / "order_review.csv",
    "combined_score": RESULTS_DIR / "combined_score.csv",
}


def _to_python_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _load_symbol_data(csv_path, symbol):
    if not csv_path.exists():
        return None

    try:
        dataframe = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None

    if "Ticker" not in dataframe.columns:
        return None

    matches = dataframe[
        dataframe["Ticker"].astype(str).str.upper() == symbol
    ]
    if matches.empty:
        return None

    return {
        column: _to_python_value(value)
        for column, value in matches.iloc[0].items()
    }


def build_stock_card(symbol):
    normalized_symbol = str(symbol).strip().upper() if symbol is not None else None

    card = {"symbol": normalized_symbol}
    for section_name, csv_path in CARD_SOURCES.items():
        card[section_name] = (
            _load_symbol_data(csv_path, normalized_symbol)
            if normalized_symbol
            else None
        )

    return card
