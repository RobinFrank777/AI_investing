"""Internal generator for the daily investor-facing research report."""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_CANDIDATE_PATH = RESULTS_DIR / "universe150_candidate_report.csv"
DEFAULT_SUMMARY_PATH = RESULTS_DIR / "universe150_ai_research_summary.csv"
DEFAULT_VALIDATION_PATH = RESULTS_DIR / "universe150_research_validation.csv"
DEFAULT_RISK_PATH = RESULTS_DIR / "universe150_risk_raw.csv"
DEFAULT_ALERT_PATH = RESULTS_DIR / "risk_alerts.csv"
DEFAULT_PIPELINE_PATH = RESULTS_DIR / "daily_research_pipeline_status.csv"
DEFAULT_OUTPUT_PATH = RESULTS_DIR / "daily_investment_report.md"
DISCLAIMER = (
    "This report is generated for research purposes only.\n"
    "It is not investment advice.\n"
    "No brokerage order is created by this workflow.\n"
    "Historical data does not guarantee future performance."
)


def _load_csv(path, label):
    if not path.is_file():
        return None, f"{label}: artifact missing."
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return None, f"{label}: artifact is empty."
    except (pd.errors.ParserError, UnicodeError, OSError) as error:
        return None, f"{label}: artifact cannot be read ({error})."
    if frame.empty:
        return frame, f"{label}: artifact contains no records."
    return frame, None


def _column(frame, *names):
    if frame is None:
        return None
    return next((name for name in names if name in frame.columns), None)


def _text(value, fallback="N/A"):
    if pd.isna(value) or not str(value).strip():
        return fallback
    return str(value).strip()


def _report_date(candidates, summaries, pipeline, now):
    for frame in (candidates, summaries):
        if frame is not None and "ReportDate" in frame and not frame.empty:
            value = _text(frame.iloc[0]["ReportDate"], "")
            if value:
                return value
    if pipeline is not None and "RunDate" in pipeline and not pipeline.empty:
        value = _text(pipeline.iloc[0]["RunDate"], "")
        if value:
            return value
    return now.strftime("%Y-%m-%d")


def _validation_data(validation):
    if validation is None:
        return "Data unavailable", [], ["Validation: Data unavailable."]
    required = {"CheckItem", "Value", "Status"}
    if not required.issubset(validation.columns):
        missing = sorted(required.difference(validation.columns))
        message = "Validation schema warning; missing: " + ", ".join(missing) + "."
        return "Data unavailable", [], [message]
    overall = validation[validation["CheckItem"].astype(str) == "OverallStatus"]
    status = "Data unavailable" if overall.empty else _text(overall.iloc[0]["Value"])
    warnings = []
    for _, row in validation.iterrows():
        row_status = _text(row["Status"], "UNKNOWN").upper()
        if row_status != "PASS":
            warnings.append(
                f"{_text(row['CheckItem'])}: {_text(row['Value'])} ({row_status})"
            )
    return status, warnings, []


def _pipeline_status(pipeline):
    if pipeline is None:
        return "Data unavailable", ["Pipeline: Data unavailable."]
    if "Status" not in pipeline:
        return "Data unavailable", ["Pipeline schema warning; missing: Status."]
    statuses = pipeline["Status"].fillna("UNKNOWN").astype(str).str.upper()
    if (statuses == "FAILED").any():
        return "FAILED", []
    if (statuses == "SKIPPED").any() or (statuses != "PASS").any():
        return "PARTIAL", []
    return "PASS", []


def _candidate_data(candidates):
    if candidates is None:
        return [], ["Candidates: Data unavailable."]
    mapping = {
        "rank": _column(candidates, "Rank"),
        "ticker": _column(candidates, "Ticker", "Symbol"),
        "score": _column(candidates, "CompositeScore"),
        "signal": _column(candidates, "Signal", "CompositeSignal"),
        "status": _column(candidates, "CandidateStatus"),
    }
    missing = [name for name in ("rank", "ticker", "score", "signal") if not mapping[name]]
    if missing:
        return [], ["Candidate schema warning; missing: " + ", ".join(missing) + "."]
    rows = []
    for _, row in candidates.head(10).iterrows():
        rows.append(
            {
                "rank": _text(row[mapping["rank"]]),
                "ticker": _text(row[mapping["ticker"]]),
                "score": _text(row[mapping["score"]]),
                "signal": _text(row[mapping["signal"]]),
                "status": _text(row[mapping["status"]]) if mapping["status"] else "N/A",
            }
        )
    return rows, []


def _summary_lookup(summaries):
    if summaries is None:
        return {}, ["AI Research Summary: Data unavailable."]
    ticker = _column(summaries, "Ticker", "Symbol")
    if ticker is None:
        return {}, ["AI Research Summary schema warning; missing: Ticker/Symbol."]
    lookup = {}
    for _, row in summaries.iterrows():
        key = _text(row[ticker], "")
        if key and key not in lookup:
            lookup[key] = {
                "tone": _text(row.get("ResearchTone")),
                "summary": _text(row.get("ResearchSummary")),
                "ai_summary": _text(row.get("AIResearchSummary")),
            }
    return lookup, []


def _alert_data(alerts):
    if alerts is None:
        return [], ["Risk Alerts: Data unavailable."]
    mapping = {
        "ticker": _column(alerts, "Ticker", "Symbol"),
        "type": _column(alerts, "AlertType", "Type"),
        "level": _column(alerts, "AlertLevel", "Severity"),
        "message": _column(alerts, "Description", "Message", "Reason"),
    }
    missing = [name for name, column in mapping.items() if column is None]
    if missing:
        return [], ["Risk alert schema warning; missing: " + ", ".join(missing) + "."]
    rows = []
    for _, row in alerts.head(10).iterrows():
        rows.append({name: _text(row[column]) for name, column in mapping.items()})
    return rows, []


def _risk_queue(risk, alerts):
    queue = []
    seen = set()
    for alert in alerts:
        if alert["level"].upper() == "WATCH":
            item = (alert["ticker"], alert["message"])
            if item not in seen:
                seen.add(item)
                queue.append(item)
    if risk is not None:
        ticker = _column(risk, "Ticker", "Symbol")
        status = _column(risk, "RiskStatus", "Status")
        if ticker and status:
            for _, row in risk.iterrows():
                risk_status = _text(row[status], "UNKNOWN").upper()
                if risk_status != "PASS":
                    item = (_text(row[ticker]), f"RiskStatus={risk_status}")
                    if item not in seen:
                        seen.add(item)
                        queue.append(item)
    return queue


def _markdown_table(headers, rows):
    if not rows:
        return "Data unavailable."
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return "\n".join(lines)


def build_daily_report(artifacts, generated_at=None):
    """Compose Markdown without recalculating research values."""
    now = generated_at or datetime.now().astimezone()
    candidates = artifacts.get("candidates")
    summaries = artifacts.get("summaries")
    validation = artifacts.get("validation")
    risk = artifacts.get("risk")
    alerts_frame = artifacts.get("alerts")
    pipeline = artifacts.get("pipeline")
    load_warnings = list(artifacts.get("load_warnings", []))

    validation_status, validation_warnings, validation_schema = _validation_data(validation)
    pipeline_status, pipeline_warnings = _pipeline_status(pipeline)
    candidate_rows, candidate_warnings = _candidate_data(candidates)
    summary_lookup, summary_warnings = _summary_lookup(summaries)
    alert_rows, alert_warnings = _alert_data(alerts_frame)
    warnings = load_warnings + validation_schema + pipeline_warnings + candidate_warnings + summary_warnings + alert_warnings

    universe = len(risk) if risk is not None else "Data unavailable"
    completed = len(candidates) if candidates is not None else "Data unavailable"
    report_date = _report_date(candidates, summaries, pipeline, now)
    quality_warning = ""
    if str(validation_status).upper() in {"PARTIAL", "FAILED"}:
        quality_warning = f"\n> **DATA QUALITY WARNING: Validation Status is {validation_status}.**\n"

    candidate_table = _markdown_table(
        ["Rank", "Ticker", "CompositeScore", "Signal", "CandidateStatus"],
        [[row["rank"], row["ticker"], row["score"], row["signal"], row["status"]] for row in candidate_rows],
    )
    summary_lines = []
    for candidate in candidate_rows:
        summary = summary_lookup.get(candidate["ticker"], {})
        summary_lines.extend(
            [
                f"### Rank {candidate['rank']} — {candidate['ticker']}",
                f"- Research Tone: {summary.get('tone', 'N/A')}",
                f"- Research Summary: {summary.get('summary', 'N/A')}",
                f"- AI Research Summary: {summary.get('ai_summary', 'N/A')}",
                "",
            ]
        )
    summary_section = "\n".join(summary_lines).rstrip() if summary_lines else "Data unavailable."
    if alerts_frame is None:
        alert_table = "Data unavailable."
    elif alert_rows:
        alert_table = _markdown_table(
            ["Symbol", "Alert Type", "Severity", "Message"],
            [[row["ticker"], row["type"], row["level"], row["message"]] for row in alert_rows],
        )
    else:
        alert_table = "No active risk alerts."
    queue = _risk_queue(risk, alert_rows)
    queue_text = "\n".join(f"- {ticker}: {reason}" for ticker, reason in queue) or "No pending items."
    insufficient = [row["ticker"] for row in alert_rows if row["type"].upper() == "HISTORY_WARNING"]
    metric_warnings = [row["message"] for row in alert_rows if row["type"].upper() == "DATA_WARNING"]
    quality_items = validation_warnings + [f"Historical data insufficient: {ticker}" for ticker in insufficient] + metric_warnings + warnings
    quality_text = "\n".join(f"- {item}" for item in quality_items) or "- No recorded data quality warnings."

    return f"""# AI_investing Daily Investment Report

Report Date: {report_date}
Generated At: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}

## 1. Market / Research Status

- Research Universe: {universe}
- Research Completed: {completed}
- Validation Status: {validation_status}
- Pipeline Status: {pipeline_status}
- Warning / Alert Count: {len(alert_rows) + len(warnings)}
{quality_warning}
## 2. Top 10 Research Candidates

{candidate_table}

## 3. Research Summary

{summary_section}

## 4. Risk Alerts

{alert_table}

## 5. Human Research Queue

{queue_text}

## 6. Data Quality

- Validation Status: {validation_status}
{quality_text}

## 7. Disclaimer

{DISCLAIMER}
"""


def generate_daily_report(
    candidate_path=None,
    summary_path=None,
    validation_path=None,
    risk_path=None,
    alert_path=None,
    pipeline_path=None,
    output_path=None,
    generated_at=None,
):
    """Load existing artifacts and write the daily Markdown report."""
    specs = {
        "candidates": (candidate_path, DEFAULT_CANDIDATE_PATH, "Candidates"),
        "summaries": (summary_path, DEFAULT_SUMMARY_PATH, "AI Research Summary"),
        "validation": (validation_path, DEFAULT_VALIDATION_PATH, "Validation"),
        "risk": (risk_path, DEFAULT_RISK_PATH, "Risk"),
        "alerts": (alert_path, DEFAULT_ALERT_PATH, "Risk Alerts"),
        "pipeline": (pipeline_path, DEFAULT_PIPELINE_PATH, "Pipeline"),
    }
    artifacts = {"load_warnings": []}
    for name, (provided, default, label) in specs.items():
        frame, warning = _load_csv(default if provided is None else Path(provided), label)
        artifacts[name] = frame
        if warning:
            artifacts["load_warnings"].append(warning)
    markdown = build_daily_report(artifacts, generated_at=generated_at)
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return {"report_path": str(path), "markdown": markdown}


def main():
    try:
        result = generate_daily_report()
    except (TypeError, ValueError, OSError) as error:
        print(f"Daily investment report error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Daily Investment Report")
    print(f"Output: {result['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
