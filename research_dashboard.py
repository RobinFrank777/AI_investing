"""Static, offline dashboard for the canonical Scale50 research report JSON."""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "scale50_factor_report.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "research_dashboard.html"
NOT_AVAILABLE = "Not available"
NOT_AVAILABLE_CANONICAL = "Not available in canonical report"
REQUIRED_SECTIONS = {
    "metadata": dict,
    "factor_model": dict,
    "ic_analysis": list,
    "group_analysis": list,
    "turnover_analysis": dict,
    "robustness_analysis": dict,
    "limitations": list,
    "conclusion": str,
}


def load_research_report(input_path=None):
    """Load and validate the canonical research-report JSON object."""
    path = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Research report JSON not found: {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid research report JSON: {path}") from error
    if not isinstance(report, dict):
        raise ValueError("Research report JSON root must be an object")
    missing = [name for name in REQUIRED_SECTIONS if name not in report]
    if missing:
        raise ValueError("Research report is missing required sections: " + ", ".join(missing))
    incorrect = [
        name for name, expected in REQUIRED_SECTIONS.items()
        if not isinstance(report[name], expected)
    ]
    if incorrect:
        raise ValueError("Research report sections have incorrect types: " + ", ".join(incorrect))
    return report


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _best_and_weakest(ic_rows):
    valid = [row for row in ic_rows if isinstance(row, dict) and _number(row.get("rank_ic")) is not None]
    if not valid:
        return NOT_AVAILABLE, NOT_AVAILABLE
    best = max(valid, key=lambda row: _number(row["rank_ic"]))
    weakest = min(valid, key=lambda row: _number(row["rank_ic"]))
    return str(best.get("horizon", NOT_AVAILABLE)), str(weakest.get("horizon", NOT_AVAILABLE))


def _stability_interpretation(score):
    value = _number(score)
    if value is None:
        return NOT_AVAILABLE
    if value >= 0.80:
        return "Relatively stable across the observed validation results."
    if value >= 0.50:
        return "Moderate stability; review horizon and regime variation."
    return "Low stability; results vary materially across observations."


def build_dashboard_data(report):
    """Select presentation fields without recalculating research metrics."""
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    for name, expected in REQUIRED_SECTIONS.items():
        if name not in report or not isinstance(report[name], expected):
            raise ValueError(f"Invalid or missing report section: {name}")
    metadata = report["metadata"]
    factor_model = report["factor_model"]
    robustness = report["robustness_analysis"]
    best, weakest = _best_and_weakest(report["ic_analysis"])
    symbol_count = metadata.get("symbol_count", NOT_AVAILABLE_CANONICAL)
    return {
        "overview": {
            "project_version": metadata.get("project_version", NOT_AVAILABLE_CANONICAL),
            "universe_mode": metadata.get("universe_mode", NOT_AVAILABLE_CANONICAL),
            "universe": metadata.get("universe", NOT_AVAILABLE),
            "symbol_count": symbol_count,
            "period": metadata.get("period", []),
            "rebalance": metadata.get("rebalance", NOT_AVAILABLE),
            "holding_periods": metadata.get("holding_periods", []),
            "factor_model": factor_model.get("name", NOT_AVAILABLE),
            "dashboard_created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "status": "Research only — not a trading recommendation or production approval.",
        },
        "factor_model": {
            "components": factor_model.get("components", []),
            "factor_ranking": factor_model.get("factor_ranking", []),
        },
        "ic_analysis": {
            "rows": report["ic_analysis"],
            "best_horizon": best,
            "weakest_horizon": weakest,
            "stability_interpretation": _stability_interpretation(
                robustness.get("stability_score")
            ),
        },
        "group_analysis": report["group_analysis"],
        "turnover_analysis": report["turnover_analysis"],
        "robustness_analysis": robustness,
        "risk_summary": {
            "maximum_drawdown": report.get("risk_summary", {}).get("maximum_drawdown", NOT_AVAILABLE),
            "sharpe_ratio": report.get("risk_summary", {}).get("sharpe_ratio", NOT_AVAILABLE),
            "group_volatility": [
                {
                    "horizon": row.get("horizon", NOT_AVAILABLE),
                    "top_20": row.get("top_20", {}).get("volatility", NOT_AVAILABLE),
                    "long_short": row.get("long_short_spread", {}).get("volatility", NOT_AVAILABLE),
                }
                for row in report["group_analysis"] if isinstance(row, dict)
            ],
            "monthly_turnover": report["turnover_analysis"].get(
                "monthly_turnover", {"mean": NOT_AVAILABLE}
            ),
        },
        "limitations": report["limitations"],
        "conclusion": report["conclusion"],
        "future_commentary": None,
    }


def _escape(value):
    return html.escape(str(value), quote=True)


def _format(value, percent=False):
    number = _number(value)
    if number is None:
        return _escape(value if value not in (None, "") else NOT_AVAILABLE)
    return f"{number:.2%}" if percent else f"{number:.4f}"


def _period(value):
    if isinstance(value, list) and len(value) == 2:
        return f"{_escape(value[0])} to {_escape(value[1])}"
    return NOT_AVAILABLE


def render_dashboard_html(dashboard_data):
    """Render deterministic standalone HTML from already-built dashboard data."""
    overview = dashboard_data["overview"]
    components = "".join(
        f"<tr><td>{_escape(row.get('factor', NOT_AVAILABLE))}</td>"
        f"<td>{_format(row.get('weight'), True)}</td>"
        f"<td>{_escape(_factor_description(row.get('factor')))}</td></tr>"
        for row in dashboard_data["factor_model"]["components"] if isinstance(row, dict)
    )
    factor_ic = "".join(
        f"<tr><td>{_escape(row.get('factor', NOT_AVAILABLE))}</td>"
        f"<td>{_format(row.get('mean_rank_ic'))}</td><td>{_format(row.get('ic_std'))}</td>"
        f"<td>{_escape(row.get('rank', NOT_AVAILABLE))}</td></tr>"
        for row in dashboard_data["factor_model"]["factor_ranking"] if isinstance(row, dict)
    )
    horizon_ic = "".join(
        f"<tr><td>{_escape(row.get('horizon', NOT_AVAILABLE))}</td>"
        f"<td>{_format(row.get('rank_ic'))}</td><td>{_format(row.get('volatility'))}</td>"
        f"<td>{_format(row.get('win_rate'), True)}</td></tr>"
        for row in dashboard_data["ic_analysis"]["rows"] if isinstance(row, dict)
    )
    groups = "".join(_group_row(row) for row in dashboard_data["group_analysis"] if isinstance(row, dict))
    consistency = "".join(
        f"<tr><td>{_escape(row.get('horizon', NOT_AVAILABLE))}</td>"
        f"<td>{_format(row.get('positive_ratio'), True)}</td>"
        f"<td>{_escape(row.get('observation_count', NOT_AVAILABLE))}</td></tr>"
        for row in dashboard_data["robustness_analysis"].get("performance_consistency", [])
        if isinstance(row, dict)
    )
    regimes = "".join(
        "<tr>" + "".join(f"<td>{_escape(value)}</td>" for value in row.values()) + "</tr>"
        for row in dashboard_data["robustness_analysis"].get("period_or_regime_checks", [])
        if isinstance(row, dict)
    ) or '<tr><td colspan="5">Not available</td></tr>'
    risk_rows = "".join(
        f"<tr><td>{_escape(row['horizon'])}</td><td>{_format(row['top_20'], True)}</td>"
        f"<td>{_format(row['long_short'], True)}</td></tr>"
        for row in dashboard_data["risk_summary"]["group_volatility"]
    )
    limitations = "".join(f"<li>{_escape(item)}</li>" for item in dashboard_data["limitations"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI_investing Research Dashboard</title><style>
:root{{--ink:#172033;--muted:#5e6878;--line:#dce2eb;--panel:#f6f8fb;--accent:#3157a4}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;margin:0;background:#eef2f7;color:var(--ink)}}main{{max-width:1180px;margin:0 auto;padding:32px}}header{{background:#172033;color:white;padding:28px;border-radius:12px}}section{{background:white;margin-top:20px;padding:24px;border-radius:12px;box-shadow:0 2px 10px #17203312}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}.card{{background:var(--panel);padding:14px;border-radius:8px}}.label{{color:var(--muted);font-size:.82rem;text-transform:uppercase}}.value{{font-weight:700;margin-top:6px}}table{{border-collapse:collapse;width:100%;margin-top:12px}}th,td{{border-bottom:1px solid var(--line);padding:10px;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{color:var(--muted)}}.notice{{border-left:4px solid var(--accent);padding-left:12px}}@media(max-width:650px){{main{{padding:14px}}section{{padding:16px;overflow-x:auto}}}}
</style></head><body><main><header><h1>AI_investing Research Dashboard</h1><p>{_escape(overview['status'])}</p></header>
<section><h2>Overview</h2><div class="grid">
{_card('Project Version', overview['project_version'])}{_card('Universe Mode', overview['universe_mode'])}{_card('Universe', overview['universe'])}{_card('Symbol Count', overview['symbol_count'])}
{_card('Backtest Period', _period(overview['period']))}{_card('Rebalance', overview['rebalance'])}{_card('Holding Periods', ' / '.join(map(str, overview['holding_periods'])) or NOT_AVAILABLE)}{_card('Factor Model', overview['factor_model'])}{_card('Dashboard Created', overview['dashboard_created_at'])}</div></section>
<section><h2>Factor Model</h2><table><tr><th>Factor</th><th>Weight</th><th>Description</th></tr>{components}</table></section>
<section><h2>IC Analysis</h2><h3>Factors</h3><table><tr><th>Factor</th><th>IC Mean</th><th>IC Std</th><th>Rank</th></tr>{factor_ic}</table><h3>Holding Horizons</h3><table><tr><th>Horizon</th><th>Rank IC</th><th>Std</th><th>Positive Ratio</th></tr>{horizon_ic}</table><p><b>Best horizon:</b> {_escape(dashboard_data['ic_analysis']['best_horizon'])}; <b>Weakest horizon:</b> {_escape(dashboard_data['ic_analysis']['weakest_horizon'])}</p><p class="notice">{_escape(dashboard_data['ic_analysis']['stability_interpretation'])}</p></section>
<section><h2>Portfolio Group Analysis</h2><table><tr><th>Horizon</th><th>Top 20%</th><th>Middle</th><th>Bottom 20%</th><th>Long-Short</th></tr>{groups}</table><p><b>Monthly turnover:</b> {_format(dashboard_data['turnover_analysis'].get('monthly_turnover', {}).get('mean'), True)}</p></section>
<section><h2>Robustness Analysis</h2><div class="grid">{_card('Stability Score', _format(dashboard_data['robustness_analysis'].get('stability_score')))}{_card('Minimum Score Coverage', _format(dashboard_data['robustness_analysis'].get('minimum_score_coverage'), True))}</div><h3>Holding-period Consistency</h3><table><tr><th>Horizon</th><th>Positive Ratio</th><th>Observations</th></tr>{consistency}</table><h3>Market Conditions / Regimes</h3><table>{regimes}</table></section>
<section><h2>Risk Summary</h2><div class="grid">{_card('Maximum Drawdown', dashboard_data['risk_summary']['maximum_drawdown'])}{_card('Sharpe Ratio', dashboard_data['risk_summary']['sharpe_ratio'])}{_card('Monthly Turnover', _format(dashboard_data['risk_summary']['monthly_turnover'].get('mean'), True))}</div><table><tr><th>Horizon</th><th>Top-group Volatility</th><th>Long-short Volatility</th></tr>{risk_rows}</table></section>
<section><h2>Research Limitations</h2><ol>{limitations}</ol></section><section><h2>Conclusion</h2><p>{_escape(dashboard_data['conclusion'])}</p><p><i>Future AI commentary interface reserved; no generated commentary is active.</i></p></section>
</main></body></html>"""


def _card(label, value):
    return f'<div class="card"><div class="label">{_escape(label)}</div><div class="value">{_escape(value)}</div></div>'


def _factor_description(name):
    return {
        "Trend": "Relative price trend strength.",
        "Momentum": "Relative medium-term price momentum.",
        "Low Volatility": "Preference for lower realized volatility.",
    }.get(name, "Description not available in canonical report.")


def _group_row(row):
    return (
        f"<tr><td>{_escape(row.get('horizon', NOT_AVAILABLE))}</td>"
        f"<td>{_format(row.get('top_20', {}).get('mean'), True)}</td>"
        f"<td>{_format(row.get('middle', {}).get('mean'), True)}</td>"
        f"<td>{_format(row.get('bottom_20', {}).get('mean'), True)}</td>"
        f"<td>{_format(row.get('long_short_spread', {}).get('mean'), True)}</td></tr>"
    )


def generate_research_dashboard(input_path=None, output_path=None):
    """Generate the offline dashboard and return its output Path."""
    report = load_research_report(input_path)
    dashboard = build_dashboard_data(report)
    rendered = render_dashboard_html(dashboard)
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return path


def main():
    try:
        output = generate_research_dashboard()
        print("AI_investing Research Dashboard")
        print(f"Generated: {output.relative_to(PROJECT_ROOT)}")
        print("Research presentation only; no trading recommendation was created.")
        return 0
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Research dashboard error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
