"""Generate the static AI_investing daily research dashboard."""

import html
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_CANDIDATE_PATH = RESULTS_DIR / "universe150_candidate_report.csv"
DEFAULT_VALIDATION_PATH = RESULTS_DIR / "universe150_research_validation.csv"
DEFAULT_RISK_PATH = RESULTS_DIR / "universe150_risk_raw.csv"
DEFAULT_ALERT_PATH = RESULTS_DIR / "risk_alerts.csv"
DEFAULT_OUTPUT_PATH = RESULTS_DIR / "daily_dashboard.html"
MINIMUM_HISTORY_ROWS = 252
RISK_METRIC_COLUMNS = (
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
)


def _load_csv(path):
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError, OSError):
        return None


def _first_column(frame, names):
    for name in names:
        if name in frame.columns:
            return name
    return None


def _text(value, fallback="Data unavailable"):
    if pd.isna(value) or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _number(value, digits=4):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Data unavailable"
    if pd.isna(number):
        return "Data unavailable"
    return f"{number:.{digits}f}"


def _validation_details(validation):
    if validation is None or validation.empty:
        return "Data unavailable", []
    required = {"CheckItem", "Value", "Status"}
    if not required.issubset(validation.columns):
        return "Data unavailable", ["Validation artifact has incompatible fields"]
    overall = validation.loc[validation["CheckItem"] == "OverallStatus"]
    overall_status = "Data unavailable" if overall.empty else _text(overall.iloc[0]["Value"])
    warnings = []
    for _, row in validation.iterrows():
        item = _text(row["CheckItem"], "Unknown validation item")
        status = _text(row["Status"], "UNKNOWN").upper()
        if status != "PASS" and item != "OverallStatus":
            warnings.append(f"{item}: {_text(row['Value'])}")
    return overall_status, warnings


def _risk_warnings(risk):
    if risk is None or risk.empty:
        return [], ["Risk artifact unavailable"]
    ticker_column = _first_column(risk, ("Ticker", "Symbol"))
    status_column = _first_column(risk, ("RiskStatus", "Status"))
    warnings = []
    global_warnings = []
    if ticker_column is None:
        return [], ["Risk artifact has no Ticker or Symbol field"]

    for _, row in risk.iterrows():
        ticker = _text(row[ticker_column], "Unknown symbol")
        reasons = []
        if "ObservationCount" not in risk.columns or pd.isna(row.get("ObservationCount")):
            reasons.append("observation count unavailable")
        else:
            observations = int(row["ObservationCount"])
            if observations < MINIMUM_HISTORY_ROWS:
                reasons.append(
                    f"insufficient history ({observations}/{MINIMUM_HISTORY_ROWS})"
                )
        missing_metrics = [
            column
            for column in RISK_METRIC_COLUMNS
            if column not in risk.columns or pd.isna(row.get(column))
        ]
        if missing_metrics:
            reasons.append("missing metrics: " + ", ".join(missing_metrics))
        if status_column is None:
            reasons.append("risk status unavailable")
        else:
            status = _text(row[status_column], "UNKNOWN").upper()
            if status != "PASS":
                reasons.append(f"RiskStatus={status}")
        if reasons:
            warnings.append({"ticker": ticker, "reason": "; ".join(reasons)})
    return warnings, global_warnings


def _top_candidates(candidates):
    if candidates is None or candidates.empty:
        return [], ["Candidate artifact unavailable"]
    mapping = {
        "rank": _first_column(candidates, ("Rank", "rank")),
        "symbol": _first_column(candidates, ("Ticker", "Symbol")),
        "score": _first_column(candidates, ("CompositeScore", "Score")),
        "signal": _first_column(candidates, ("Signal", "CompositeSignal")),
        "validation": _first_column(
            candidates,
            ("CandidateStatus", "ResearchStatus", "RiskStatus", "Validation"),
        ),
    }
    missing = [name for name, column in mapping.items() if column is None]
    if missing:
        return [], ["Candidate fields unavailable: " + ", ".join(missing)]
    rows = []
    for _, row in candidates.head(10).iterrows():
        rows.append(
            {
                "rank": _text(row[mapping["rank"]]),
                "symbol": _text(row[mapping["symbol"]]),
                "score": _number(row[mapping["score"]]),
                "signal": _text(row[mapping["signal"]]),
                "validation": _text(row[mapping["validation"]]),
            }
        )
    return rows, []


def _risk_alerts(alerts):
    if alerts is None:
        return [], ["Risk alert artifact unavailable"]
    if alerts.empty:
        return [], []
    required = {"Symbol", "AlertType", "AlertLevel", "Description"}
    if not required.issubset(alerts.columns):
        return [], ["Risk alert artifact has incompatible fields"]
    rows = []
    for _, row in alerts.head(10).iterrows():
        rows.append(
            {
                "symbol": _text(row["Symbol"]),
                "type": _text(row["AlertType"]),
                "level": _text(row["AlertLevel"]),
                "description": _text(row["Description"]),
            }
        )
    return rows, []


def build_dashboard_data(candidates, validation, risk, alerts=None):
    """Prepare display-only dashboard values from existing artifacts."""
    validation_status, validation_warnings = _validation_details(validation)
    risk_items, risk_global_warnings = _risk_warnings(risk)
    top_candidates, candidate_warnings = _top_candidates(candidates)
    alert_items, alert_warnings = _risk_alerts(alerts)

    universe_size = "Data unavailable"
    if risk is not None:
        universe_size = int(len(risk))
    elif candidates is not None:
        universe_size = int(len(candidates))
    completed = "Data unavailable" if candidates is None else int(len(candidates))
    report_date = "Data unavailable"
    if candidates is not None and not candidates.empty and "ReportDate" in candidates:
        report_date = _text(candidates["ReportDate"].iloc[0])

    global_warnings = (
        validation_warnings
        + risk_global_warnings
        + candidate_warnings
        + alert_warnings
    )
    warning_count = len(alert_items) + len(alert_warnings)
    return {
        "report_date": report_date,
        "universe_size": universe_size,
        "completed": completed,
        "validation_status": validation_status,
        "warning_count": warning_count,
        "top_candidates": top_candidates,
        "alert_items": alert_items,
        "risk_items": risk_items,
        "global_warnings": global_warnings,
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "artifact_sources": {
            "candidate_report": candidates is not None,
            "validation": validation is not None,
            "risk_raw": risk is not None,
        },
    }


def _candidate_rows(candidates):
    if not candidates:
        return '<tr><td colspan="5" class="empty">Data unavailable</td></tr>'
    return "\n".join(
        "<tr>"
        f"<td>{html.escape(item['rank'])}</td>"
        f"<td>{html.escape(item['symbol'])}</td>"
        f"<td>{html.escape(item['score'])}</td>"
        f"<td><span class=\"badge\">{html.escape(item['signal'])}</span></td>"
        f"<td>{html.escape(item['validation'])}</td>"
        "</tr>"
        for item in candidates
    )


def _warning_items(items, global_warnings):
    content = [
        f"<li><strong>{html.escape(item['ticker'])}</strong>: "
        f"{html.escape(item['reason'])}</li>"
        for item in items
    ]
    content.extend(f"<li>{html.escape(item)}</li>" for item in global_warnings)
    return "\n".join(content) if content else "<li>No pending items</li>"


def _alert_rows(alerts):
    if not alerts:
        return '<tr><td colspan="4" class="empty">No risk alerts</td></tr>'
    return "\n".join(
        "<tr>"
        f"<td>{html.escape(item['symbol'])}</td>"
        f"<td>{html.escape(item['type'])}</td>"
        f"<td><span class=\"level\">{html.escape(item['level'])}</span></td>"
        f"<td>{html.escape(item['description'])}</td>"
        "</tr>"
        for item in alerts
    )


def _source_items(sources):
    return "\n".join(
        f"<li><strong>{html.escape(name)}</strong>: "
        f"{'Available' if available else 'Data unavailable'}</li>"
        for name, available in sources.items()
    )


def render_dashboard_html(data):
    """Render a fully standalone daily dashboard."""
    validation_class = str(data["validation_status"]).strip().lower()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI_investing Daily Research Dashboard</title>
  <style>
    :root {{ color-scheme: light; --ink:#172033; --muted:#64748b; --line:#dbe3ee;
      --panel:#ffffff; --page:#f4f7fb; --accent:#2563eb; --warn:#b45309; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--page); color:var(--ink);
      font:15px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1120px; margin:0 auto; padding:32px 20px 48px; }}
    h1 {{ margin:0 0 4px; font-size:30px; }}
    h2 {{ margin:0 0 18px; font-size:20px; }}
    .subtitle {{ color:var(--muted); margin-bottom:26px; }}
    section {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
      padding:22px; margin:18px 0; box-shadow:0 5px 18px rgba(15,23,42,.04); }}
    .cards {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; }}
    .card {{ border:1px solid var(--line); border-radius:10px; padding:14px; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .value {{ font-size:22px; font-weight:700; margin-top:5px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ text-align:left; padding:11px 9px; border-bottom:1px solid var(--line); }}
    th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
    .badge {{ display:inline-block; min-width:30px; text-align:center; border-radius:999px;
      color:#fff; background:var(--accent); padding:2px 9px; font-weight:700; }}
    .level {{ font-weight:700; color:var(--warn); }}
    .notice {{ border-left:4px solid var(--warn); background:#fff7ed; padding:12px 14px;
      margin-top:16px; color:#7c2d12; }}
    ul {{ margin:0; padding-left:22px; }}
    li + li {{ margin-top:8px; }}
    .empty {{ text-align:center; color:var(--muted); }}
    footer {{ color:var(--muted); margin-top:24px; font-size:13px; }}
    @media (max-width:800px) {{ .cards {{ grid-template-columns:1fr 1fr; }}
      section {{ overflow-x:auto; }} }}
  </style>
</head>
<body><main>
  <h1>AI_investing Daily Research Dashboard</h1>
  <div class="subtitle">Report Date: {html.escape(str(data['report_date']))} · Generated At: {html.escape(data['generated_at'])} · Research diagnostics only</div>

  <section>
    <h2>Market Status</h2>
    <div class="cards">
      <div class="card"><div class="label">Research Universe</div><div class="value">{html.escape(str(data['universe_size']))}</div></div>
      <div class="card"><div class="label">Research Completed</div><div class="value">{html.escape(str(data['completed']))}</div></div>
      <div class="card"><div class="label">Validation</div><div class="value {html.escape(validation_class)}">{html.escape(str(data['validation_status']))}</div></div>
      <div class="card"><div class="label">Warnings</div><div class="value">{data['warning_count']}</div></div>
      <div class="card"><div class="label">Scope</div><div class="value">Top 10</div></div>
    </div>
    <div class="notice">Pipeline completion and data quality are separate. RiskStatus=PASS means metrics were calculated; it does not mean low risk.</div>
  </section>

  <section>
    <h2>Risk Alerts</h2>
    <table><thead><tr><th>Symbol</th><th>Type</th><th>Level</th><th>Description</th></tr></thead>
      <tbody>{_alert_rows(data['alert_items'])}</tbody>
    </table>
  </section>

  <section>
    <h2>Top Candidates</h2>
    <table><thead><tr><th>Rank</th><th>Symbol</th><th>Score</th><th>Signal</th><th>Validation</th></tr></thead>
      <tbody>{_candidate_rows(data['top_candidates'])}</tbody>
    </table>
  </section>

  <section>
    <h2>Risk Watchlist</h2>
    <ul>{_warning_items(data['risk_items'], data['global_warnings'])}</ul>
  </section>

  <section>
    <h2>Human Research Queue</h2>
    <ul>{_warning_items(
        [
            {"ticker": item["symbol"], "reason": item["description"]}
            for item in data["alert_items"]
            if item["level"].upper() == "WATCH"
        ],
        [],
    )}</ul>
  </section>

  <section>
    <h2>Data Quality</h2>
    <ul>{_warning_items([], data['global_warnings'])}</ul>
    <h3>Artifact Sources</h3>
    <ul>{_source_items(data['artifact_sources'])}</ul>
  </section>

  <footer>No factor, rank, signal, or risk metric is recalculated by this dashboard. Manual research is required.</footer>
</main></body></html>
"""


def generate_daily_dashboard(
    candidate_path=None,
    validation_path=None,
    risk_path=None,
    alert_path=None,
    output_path=None,
):
    """Load existing artifacts and write the static dashboard."""
    candidates = _load_csv(
        DEFAULT_CANDIDATE_PATH if candidate_path is None else Path(candidate_path)
    )
    validation = _load_csv(
        DEFAULT_VALIDATION_PATH if validation_path is None else Path(validation_path)
    )
    risk = _load_csv(DEFAULT_RISK_PATH if risk_path is None else Path(risk_path))
    alerts = _load_csv(DEFAULT_ALERT_PATH if alert_path is None else Path(alert_path))
    data = build_dashboard_data(candidates, validation, risk, alerts)
    rendered = render_dashboard_html(data)
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return {"output_path": str(path), "data": data}


def main():
    try:
        result = generate_daily_dashboard()
    except (ValueError, TypeError, OSError) as error:
        print(f"Daily dashboard error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Daily Research Dashboard")
    print(f"Output: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
