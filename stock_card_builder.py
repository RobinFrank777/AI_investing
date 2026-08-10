from pathlib import Path

import pandas as pd

from investment_profile_loader import load_company_profile


PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"

CARD_SOURCES = {
    "top_opportunity": RESULTS_DIR / "top10.csv",
    "model_portfolio": RESULTS_DIR / "model_portfolio.csv",
    "order_review": RESULTS_DIR / "order_review.csv",
    "combined_score": RESULTS_DIR / "combined_score.csv",
}

INVESTMENT_PROFILE_FIELDS = (
    ("company_name", "company"),
    ("business_model", "business_model"),
    ("investment_thesis", "investment_thesis"),
    ("moat_score", "moat_score"),
    ("growth_driver", "growth_driver"),
    ("risk_factor", "risk_factor"),
    ("investment_stage", "investment_stage"),
    ("investor_rating", "investor_rating"),
)


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


def _load_investment_profile(symbol):
    try:
        profile = load_company_profile(symbol)
    except (OSError, ValueError):
        return None

    if profile is None:
        return None
    return {
        card_field: _to_python_value(profile.get(source_field))
        for card_field, source_field in INVESTMENT_PROFILE_FIELDS
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
    card["investment_profile"] = (
        _load_investment_profile(normalized_symbol) if normalized_symbol else None
    )

    return card
