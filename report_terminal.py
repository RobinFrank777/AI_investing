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


def _top_opportunities_content(dataframe, combined_scores=None):
    display_dataframe = dataframe.copy()
    replacements = {}
    links = []
    cards = []

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

        try:
            research = build_research_summary(symbol)
            stance = str(research.get("stance") or "INSUFFICIENT DATA").strip()
            summary = str(research.get("summary") or "N/A").strip()
        except Exception:
            stance = "INSUFFICIENT DATA"
            summary = "Research summary is unavailable for this symbol."

        row = display_dataframe.iloc[row_number]
        score = _combined_score_for(symbol, row, combined_scores)
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

    display_dataframe["Research Card"] = links
    table_html = display_dataframe.to_html(index=False, border=0, na_rep="")
    for placeholder, link_html in replacements.items():
        table_html = table_html.replace(placeholder, link_html)
    return table_html + f'<div class="opportunity-list">{"".join(cards)}</div>'


def build_html(report_data):
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    combined_scores = next(
        (
            dataframe
            for section_title, dataframe in report_data
            if section_title == "Combined Score"
        ),
        None,
    )
    sections_html = "\n".join(
        f"""
        <section>
            <h2>{section_title}</h2>
            <div class="table-container">
                {
                    _top_opportunities_content(dataframe, combined_scores)
                    if section_title == "Top Opportunities"
                    else dataframe.to_html(index=False, border=0, na_rep="")
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
                <div class="status-value pass">PASS</div>
            </div>
        </div>
    </section>

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
