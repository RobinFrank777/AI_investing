from datetime import datetime
from html import escape
import math
from pathlib import Path
import sys

from research_summary import build_research_summary
from stock_card_builder import build_stock_card


PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CARDS_DIR = PROJECT_ROOT / "reports" / "cards"

TEMPLATE_PATH = TEMPLATES_DIR / "stock_card.html"
CSS_PATH = TEMPLATES_DIR / "report.css"

SECTION_CONFIG = (
    (
        "TOP_OPPORTUNITY",
        "top_opportunity",
        "No matching Top Opportunity record.",
    ),
    ("COMBINED_SCORE", "combined_score", "No matching Combined Score record."),
    ("MODEL_PORTFOLIO", "model_portfolio", "No matching Model Portfolio record."),
    ("ORDER_REVIEW", "order_review", "No matching Order Review record."),
)
INVESTMENT_PROFILE_DISPLAY_FIELDS = (
    ("Company", "company_name"),
    ("Business Model", "business_model"),
    ("Investment Thesis", "investment_thesis"),
    ("Moat Score", "moat_score"),
    ("Growth Driver", "growth_driver"),
    ("Risk Factor", "risk_factor"),
    ("Investment Stage", "investment_stage"),
    ("Investor Rating", "investor_rating"),
)


def _display_value(value):
    if value is None:
        return "N/A"
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except (TypeError, ValueError):
        pass
    return escape(str(value), quote=True)


def _build_table(record, empty_message):
    if record is None:
        return f'<p class="empty">{escape(empty_message)}</p>'

    rows = "\n".join(
        "<tr>"
        f'<th scope="row">{escape(str(field), quote=True)}</th>'
        f"<td>{_display_value(value)}</td>"
        "</tr>"
        for field, value in record.items()
    )
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Field</th><th>Value</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def _build_research_list(items, css_class, empty_message):
    if not isinstance(items, (list, tuple)):
        items = []
    display_items = [
        _display_value(item)
        for item in items
        if _display_value(item) != "N/A"
    ]
    if not display_items:
        return f'<p class="empty">{escape(empty_message)}</p>'
    list_items = "".join(f"<li>{item}</li>" for item in display_items)
    return f'<ul class="{css_class}">{list_items}</ul>'


def _build_investment_profile(profile):
    if profile is None:
        return '<p class="empty">Investment Profile unavailable.</p>'
    return "\n".join(
        "<p>"
        f"<strong>{escape(label, quote=True)}:</strong> "
        f"{_display_value(profile.get(field))}"
        "</p>"
        for label, field in INVESTMENT_PROFILE_DISPLAY_FIELDS
    )


def generate_stock_card_report(symbol):
    normalized_symbol = str(symbol).strip().upper() if symbol is not None else ""
    if not normalized_symbol:
        raise ValueError("Stock symbol must not be empty.")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    report_css = CSS_PATH.read_text(encoding="utf-8")
    stock_card = build_stock_card(normalized_symbol)
    research_summary = build_research_summary(normalized_symbol)
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    escaped_symbol = escape(normalized_symbol, quote=True)

    replacements = {
        "{{PAGE_TITLE}}": f"{escaped_symbol} Stock Research Card",
        "{{REPORT_CSS}}": report_css,
        "{{SYMBOL}}": escaped_symbol,
        "{{GENERATED_TIME}}": escape(generated_time),
        "{{PROJECT_VERSION}}": _display_value(
            research_summary.get("project_version")
        ),
        "{{RESEARCH_STANCE}}": _display_value(research_summary.get("stance")),
        "{{RESEARCH_STRENGTHS}}": _build_research_list(
            research_summary.get("strengths"),
            "strengths-list",
            "No identified strengths from the current rules.",
        ),
        "{{RESEARCH_RISKS}}": _build_research_list(
            research_summary.get("risks"),
            "risks-list",
            "No additional rule-based risks were identified.",
        ),
        "{{RESEARCH_SUMMARY}}": _display_value(research_summary.get("summary")),
        "{{INVESTMENT_PROFILE}}": _build_investment_profile(
            stock_card.get("investment_profile")
        ),
        "{{MANUAL_REVIEW_WARNING}}": (
            '<p class="manual-review-warning">'
            "Manual review is required before any real trade."
            "</p>"
            if research_summary.get("manual_review_required") is True
            else ""
        ),
    }
    for placeholder, card_key, empty_message in SECTION_CONFIG:
        replacements[f"{{{{{placeholder}}}}}"] = _build_table(
            stock_card.get(card_key),
            empty_message,
        )

    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CARDS_DIR / f"{normalized_symbol}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1:
        print("Usage:")
        print("python stock_card_report.py SYMBOL")
        return 1

    output_path = generate_stock_card_report(arguments[0])
    print("Stock card generated:")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
