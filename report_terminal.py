from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from config import PROJECT_VERSION
from research_summary import build_research_summary


PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "ai_terminal_report.html"
PIPELINE_STATUS = "PASS"

REPORT_SECTIONS = [
    ("Top Opportunities", RESULTS_DIR / "top10.csv"),
    ("Model Portfolio", RESULTS_DIR / "model_portfolio.csv"),
    ("Order Review", RESULTS_DIR / "order_review.csv"),
    ("Combined Score", RESULTS_DIR / "combined_score.csv"),
]


def load_report_data():
    return [
        (section_title, pd.read_csv(csv_path))
        for section_title, csv_path in REPORT_SECTIONS
    ]


def _normalized_symbol(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def _safe_score(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if pd.notna(score) and score not in (float("inf"), float("-inf")) else None


def _combined_score_for(symbol, row, combined_scores):
    score = _safe_score(row.get("CombinedScore"))
    if score is not None or combined_scores is None or "Ticker" not in combined_scores:
        return score

    matches = combined_scores[
        combined_scores["Ticker"].map(_normalized_symbol) == symbol
    ]
    if matches.empty or "CombinedScore" not in matches:
        return None
    return _safe_score(matches.iloc[0]["CombinedScore"])


def _stance_class(stance):
    return {
        "BUY CANDIDATE": "stance-buy",
        "HOLD / REVIEW": "stance-hold",
        "REDUCE / AVOID": "stance-reduce",
        "INSUFFICIENT DATA": "stance-insufficient",
    }.get(stance, "stance-insufficient")


def _table_with_card_links(dataframe):
    display_dataframe = dataframe.copy()
    replacements = {}
    links = []

    for row_number, ticker in enumerate(display_dataframe.get("Ticker", [])):
        symbol = _normalized_symbol(ticker)
        if not symbol:
            links.append("")
            continue

        placeholder = f"RESEARCH_CARD_LINK_{row_number}"
        href = f"cards/{quote(symbol, safe='')}.html"
        escaped_href = escape(href, quote=True)
        replacements[placeholder] = f'<a href="{escaped_href}">View Card</a>'
        links.append(placeholder)

    display_dataframe["Research Card"] = links
    table_html = display_dataframe.to_html(index=False, border=0, na_rep="")
    for placeholder, link_html in replacements.items():
        table_html = table_html.replace(placeholder, link_html)
    return table_html


def _build_top_opportunity_research(dataframe, combined_scores=None):
    research_items = []
    for row_number, ticker in enumerate(dataframe.get("Ticker", [])):
        symbol = _normalized_symbol(ticker)
        if not symbol:
            continue

        href = f"cards/{quote(symbol, safe='')}.html"

        try:
            research = build_research_summary(symbol)
            stance = str(research.get("stance") or "INSUFFICIENT DATA").strip()
            summary = str(research.get("summary") or "N/A").strip()
        except Exception:
            stance = "INSUFFICIENT DATA"
            summary = "Research summary is unavailable for this symbol."

        row = dataframe.iloc[row_number]
        score = _combined_score_for(symbol, row, combined_scores)
        research_items.append(
            {
                "symbol": symbol,
                "stance": stance,
                "summary": summary,
                "combined_score": score,
                "href": href,
            }
        )
    return research_items


def build_dashboard_metrics(
    research_items,
    model_portfolio,
    pipeline_status=PIPELINE_STATUS,
):
    stance_counts = {
        "BUY CANDIDATE": 0,
        "HOLD / REVIEW": 0,
        "REDUCE / AVOID": 0,
        "INSUFFICIENT DATA": 0,
    }
    valid_scores = []
    for item in research_items:
        stance = item.get("stance")
        if stance in stance_counts:
            stance_counts[stance] += 1
        else:
            stance_counts["INSUFFICIENT DATA"] += 1
        score = _safe_score(item.get("combined_score"))
        if score is not None:
            valid_scores.append((item.get("symbol", ""), score))

    if valid_scores:
        average_score = f"{sum(score for _, score in valid_scores) / len(valid_scores):.2f}"
        highest_symbol, highest_value = max(valid_scores, key=lambda entry: entry[1])
        highest_score = f"{highest_symbol} / {highest_value:.2f}"
    else:
        average_score = "N/A"
        highest_score = "N/A"

    portfolio_count = sum(
        1
        for ticker in model_portfolio.get("Ticker", [])
        if _normalized_symbol(ticker)
    )
    return {
        "pipeline_status": pipeline_status,
        "top_opportunities_count": len(research_items),
        "buy_candidate_count": stance_counts["BUY CANDIDATE"],
        "hold_review_count": stance_counts["HOLD / REVIEW"],
        "reduce_avoid_count": stance_counts["REDUCE / AVOID"],
        "insufficient_data_count": stance_counts["INSUFFICIENT DATA"],
        "average_combined_score": average_score,
        "highest_score": highest_score,
        "model_portfolio_count": portfolio_count,
        "research_card_link_count": len(research_items),
    }


def _top_opportunities_content(dataframe, research_items):
    cards = []
    for item in research_items:
        symbol = item["symbol"]
        stance = item["stance"]
        summary = item["summary"]
        score = item["combined_score"]
        escaped_href = escape(item["href"], quote=True)
        score_text = f"{score:.2f}" if score is not None else "N/A"
        cards.append(
            f"""
            <article class="opportunity-card">
                <div class="opportunity-header">
                    <h3>{escape(symbol, quote=True)}</h3>
                    <span class="stance {_stance_class(stance)}">{escape(stance, quote=True)}</span>
                </div>
                <div class="score"><strong>Combined Score:</strong> {escape(score_text)}</div>
                <p class="summary">{escape(summary, quote=True)}</p>
                <a class="card-link" href="{escaped_href}">View Card</a>
            </article>
            """
        )

    table_html = _table_with_card_links(dataframe)
    return table_html + f'<div class="opportunity-list">{"".join(cards)}</div>'


def _dashboard_html(metrics, generated_time):
    metric_rows = (
        ("Pipeline Status", metrics["pipeline_status"], "metric-pass"),
        ("Top Opportunities", metrics["top_opportunities_count"], ""),
        ("BUY CANDIDATE", metrics["buy_candidate_count"], "metric-buy"),
        ("HOLD / REVIEW", metrics["hold_review_count"], "metric-hold"),
        ("REDUCE / AVOID", metrics["reduce_avoid_count"], "metric-reduce"),
        (
            "INSUFFICIENT DATA",
            metrics["insufficient_data_count"],
            "metric-insufficient",
        ),
        ("Average Combined Score", metrics["average_combined_score"], ""),
        ("Highest Score", metrics["highest_score"], ""),
        ("Model Portfolio Count", metrics["model_portfolio_count"], ""),
        ("Research Card Links", metrics["research_card_link_count"], ""),
        ("Generated Time", generated_time, ""),
    )
    cards = "".join(
        f"""
        <div class="metric-card">
            <div class="metric-label">{escape(label, quote=True)}</div>
            <div class="metric-value {css_class}">{escape(str(value), quote=True)}</div>
        </div>
        """
        for label, value, css_class in metric_rows
    )
    return f"""
    <section class="dashboard">
        <h2>Today's Research Dashboard</h2>
        <div class="dashboard-grid">{cards}</div>
    </section>
    """


def build_html(report_data):
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_opportunities = next(
        (dataframe for title, dataframe in report_data if title == "Top Opportunities"),
        pd.DataFrame(),
    )
    model_portfolio = next(
        (dataframe for title, dataframe in report_data if title == "Model Portfolio"),
        pd.DataFrame(),
    )
    combined_scores = next(
        (
            dataframe
            for section_title, dataframe in report_data
            if section_title == "Combined Score"
        ),
        None,
    )
    research_items = _build_top_opportunity_research(
        top_opportunities,
        combined_scores,
    )
    dashboard_metrics = build_dashboard_metrics(research_items, model_portfolio)
    dashboard_html = _dashboard_html(dashboard_metrics, generated_time)
    sections_html = "\n".join(
        f"""
        <section>
            <h2>{section_title}</h2>
            <div class="table-container">
                {
                    _top_opportunities_content(dataframe, research_items)
                    if section_title == "Top Opportunities"
                    else (
                        _table_with_card_links(dataframe)
                        if section_title == "Model Portfolio"
                        else dataframe.to_html(index=False, border=0, na_rep="")
                    )
                }
            </div>
        </section>
        """
        for section_title, dataframe in report_data
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI_investing Daily Research Terminal</title>
    <style>
        body {{
            margin: 0;
            padding: 32px;
            background: #f4f6f8;
            color: #1f2933;
            font-family: Arial, sans-serif;
        }}
        main {{ max-width: 1600px; margin: 0 auto; }}
        h1 {{ margin: 0 0 24px; }}
        section {{
            margin-bottom: 24px;
            padding: 24px;
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 8px;
        }}
        h2 {{ margin-top: 0; }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}
        .status-label {{ color: #52606d; font-size: 14px; }}
        .status-value {{ margin-top: 6px; font-size: 18px; font-weight: bold; }}
        .pass {{ color: #16803c; }}
        .table-container {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th, td {{ padding: 9px 12px; border: 1px solid #d9e2ec; white-space: nowrap; }}
        th {{ background: #243b53; color: #ffffff; text-align: left; }}
        tbody tr:nth-child(even) {{ background: #f8fafc; }}
        .opportunity-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }}
        .opportunity-card {{
            padding: 18px;
            border: 1px solid #d9e2ec;
            border-radius: 6px;
            background: #f8fafc;
        }}
        .opportunity-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }}
        .opportunity-header h3 {{ margin: 0; }}
        .stance {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .stance-buy {{ background: #d9f2e3; color: #126b34; }}
        .stance-hold {{ background: #fff1c7; color: #7a5600; }}
        .stance-reduce {{ background: #fbe0e0; color: #9b1c1c; }}
        .stance-insufficient {{ background: #e4e7eb; color: #52606d; }}
        .score {{ margin-top: 14px; }}
        .opportunity-card .summary {{ color: #3e4c59; line-height: 1.5; }}
        .card-link {{ color: #145da0; font-weight: bold; }}
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 14px;
        }}
        .metric-card {{
            padding: 16px;
            background: #f8fafc;
            border: 1px solid #d9e2ec;
            border-radius: 6px;
        }}
        .metric-label {{ color: #52606d; font-size: 13px; }}
        .metric-value {{ margin-top: 6px; font-size: 20px; font-weight: bold; }}
        .metric-pass, .metric-buy {{ color: #16803c; }}
        .metric-hold {{ color: #8a6100; }}
        .metric-reduce {{ color: #b42318; }}
        .metric-insufficient {{ color: #52606d; }}
    </style>
</head>
<body>
<main>
    <h1>AI_investing Daily Research Terminal</h1>

    <section>
        <h2>System Status</h2>
        <div class="status-grid">
            <div>
                <div class="status-label">Version</div>
                <div class="status-value">{escape(PROJECT_VERSION, quote=True)}</div>
            </div>
            <div>
                <div class="status-label">Generated Time</div>
                <div class="status-value">{generated_time}</div>
            </div>
            <div>
                <div class="status-label">Pipeline Status</div>
                <div class="status-value pass">{escape(PIPELINE_STATUS, quote=True)}</div>
            </div>
        </div>
    </section>

    {dashboard_html}

    {sections_html}
</main>
</body>
</html>
"""


def generate_terminal_report():
    report_data = load_report_data()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_html(report_data), encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":
    output_path = generate_terminal_report()
    print(f"Research Terminal report generated: {output_path}")
