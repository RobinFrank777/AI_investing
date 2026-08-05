"""Build deterministic, human-reviewable research summaries for stocks."""

import math

from config import PROJECT_VERSION
from stock_card_builder import build_stock_card


_DATA_SECTIONS = (
    "top_opportunity",
    "model_portfolio",
    "order_review",
    "combined_score",
)


def _safe_number(value):
    """Return a finite float, or None when value is not a usable number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _field(section, name):
    return section.get(name) if isinstance(section, dict) else None


def _normalized_text(value):
    return str(value).strip().upper() if value is not None else ""


def determine_stance(card):
    """Classify a stock card using the documented, ordered stance rules."""
    order_review = card.get("order_review")
    combined_score = card.get("combined_score")
    action = _normalized_text(_field(order_review, "Action"))
    review_status = _normalized_text(_field(order_review, "ReviewStatus"))
    score = _safe_number(_field(combined_score, "CombinedScore"))

    if action in {"SELL", "REDUCE"} or review_status == "FAIL":
        return "REDUCE / AVOID"
    if action == "BUY" and review_status == "PASS" and score is not None and score >= 70:
        return "BUY CANDIDATE"
    if action == "HOLD" or any(card.get(name) is not None for name in _DATA_SECTIONS):
        return "HOLD / REVIEW"
    return "INSUFFICIENT DATA"


def _build_strengths(card):
    combined_score = card.get("combined_score")
    order_review = card.get("order_review")
    model_portfolio = card.get("model_portfolio")
    score = _safe_number(_field(combined_score, "CombinedScore"))
    strengths = []

    if score is not None and score >= 80:
        strengths.append("Combined score is very strong.")
    elif score is not None and score >= 70:
        strengths.append("Combined score is strong.")
    if _normalized_text(_field(combined_score, "FundamentalRating")) in {"GOOD", "STRONG"}:
        strengths.append("Fundamental rating is positive.")
    if _normalized_text(_field(order_review, "ReviewStatus")) == "PASS":
        strengths.append("Order review passed the current system checks.")
    if card.get("top_opportunity") is not None:
        strengths.append("The stock is included in the current Top Opportunities list.")
    if _normalized_text(_field(model_portfolio, "PortfolioRole")) == "CANDIDATE":
        strengths.append("The stock is included as a model portfolio candidate.")
    return strengths


def _build_risks(card):
    combined_score = card.get("combined_score")
    order_review = card.get("order_review")
    score = _safe_number(_field(combined_score, "CombinedScore"))
    risks = []

    if combined_score is None or score is None:
        risks.append("Combined score data is unavailable.")
    if order_review is None:
        risks.append("Order review data is unavailable.")
    elif _normalized_text(_field(order_review, "ReviewStatus")) == "FAIL":
        risks.append("Order review did not pass the current system checks.")
    if score is not None and score < 60:
        risks.append("Combined score is below the preferred candidate threshold.")
    if card.get("top_opportunity") is None:
        risks.append("The stock is not included in the current Top Opportunities list.")
    if card.get("model_portfolio") is None:
        risks.append("The stock is not included in the current model portfolio output.")
    return risks


def _build_summary(symbol, stance, strengths, risks):
    sentences = [
        f"{symbol} is classified as a {stance} based on the current deterministic research rules."
    ]
    sentences.extend(strengths)
    sentences.extend(risks)
    sentences.append(
        "This output identifies a research candidate for review only and is not investment approval."
    )
    return " ".join(sentences)


def build_research_summary(symbol):
    """Return a deterministic research summary without writing any files."""
    normalized_symbol = str(symbol).strip().upper() if symbol is not None else ""
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")

    card = build_stock_card(normalized_symbol)
    if not isinstance(card, dict):
        card = {}
    stance = determine_stance(card)
    strengths = _build_strengths(card)
    risks = _build_risks(card)

    return {
        "symbol": normalized_symbol,
        "project_version": PROJECT_VERSION,
        "stance": stance,
        "strengths": strengths,
        "risks": risks,
        "summary": _build_summary(normalized_symbol, stance, strengths, risks),
        "manual_review_required": True,
    }
