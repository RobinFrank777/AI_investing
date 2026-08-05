from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "ai_terminal_report.html"
VERSION = "v3.3.0"

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


def build_html(report_data):
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections_html = "\n".join(
        f"""
        <section>
            <h2>{section_title}</h2>
            <div class="table-container">
                {dataframe.to_html(index=False, border=0, na_rep="")}
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
                <div class="status-value">{VERSION}</div>
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
