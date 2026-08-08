"""Build factual user-layer alerts from existing validation and risk artifacts."""

import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_VALIDATION_PATH = RESULTS_DIR / "universe150_research_validation.csv"
DEFAULT_RISK_PATH = RESULTS_DIR / "universe150_risk_raw.csv"
DEFAULT_OUTPUT_PATH = RESULTS_DIR / "risk_alerts.csv"
OUTPUT_COLUMNS = ("Symbol", "AlertType", "AlertLevel", "Description")
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


def _text(value, fallback="UNKNOWN"):
    if pd.isna(value) or str(value).strip() == "":
        return fallback
    return str(value).strip()


def build_risk_alerts(validation, risk):
    """Return factual alerts without calculating a risk score."""
    alerts = []
    if validation is None:
        alerts.append(
            {
                "Symbol": "SYSTEM",
                "AlertType": "DATA_WARNING",
                "AlertLevel": "INFO",
                "Description": "Validation artifact is unavailable.",
            }
        )
    elif not validation.empty:
        required = {"CheckItem", "Value", "Status"}
        if not required.issubset(validation.columns):
            alerts.append(
                {
                    "Symbol": "SYSTEM",
                    "AlertType": "DATA_WARNING",
                    "AlertLevel": "INFO",
                    "Description": "Validation artifact has incompatible fields.",
                }
            )
        else:
            for _, row in validation.iterrows():
                status = _text(row["Status"]).upper()
                if status != "PASS":
                    item = _text(row["CheckItem"])
                    value = _text(row["Value"])
                    alerts.append(
                        {
                            "Symbol": "SYSTEM",
                            "AlertType": "DATA_WARNING",
                            "AlertLevel": "INFO",
                            "Description": f"Validation {item} is {value} ({status}).",
                        }
                    )

    if risk is None:
        alerts.append(
            {
                "Symbol": "SYSTEM",
                "AlertType": "DATA_WARNING",
                "AlertLevel": "INFO",
                "Description": "Risk artifact is unavailable.",
            }
        )
        return pd.DataFrame(alerts, columns=OUTPUT_COLUMNS)
    if risk.empty:
        return pd.DataFrame(alerts, columns=OUTPUT_COLUMNS)

    ticker_column = "Ticker" if "Ticker" in risk else "Symbol" if "Symbol" in risk else None
    status_column = "RiskStatus" if "RiskStatus" in risk else "Status" if "Status" in risk else None
    if ticker_column is None:
        alerts.append(
            {
                "Symbol": "SYSTEM",
                "AlertType": "DATA_WARNING",
                "AlertLevel": "INFO",
                "Description": "Risk artifact has no Ticker or Symbol field.",
            }
        )
        return pd.DataFrame(alerts, columns=OUTPUT_COLUMNS)

    for _, row in risk.iterrows():
        symbol = _text(row[ticker_column], "UNKNOWN")
        manual_reasons = []
        if "ObservationCount" not in risk or pd.isna(row.get("ObservationCount")):
            alerts.append(
                {
                    "Symbol": symbol,
                    "AlertType": "DATA_WARNING",
                    "AlertLevel": "INFO",
                    "Description": "Observation count is unavailable.",
                }
            )
            manual_reasons.append("observation count is unavailable")
        else:
            observations = int(row["ObservationCount"])
            if observations < MINIMUM_HISTORY_ROWS:
                description = (
                    f"Historical data is insufficient: {observations} of "
                    f"{MINIMUM_HISTORY_ROWS} required rows."
                )
                alerts.append(
                    {
                        "Symbol": symbol,
                        "AlertType": "HISTORY_WARNING",
                        "AlertLevel": "INFO",
                        "Description": description,
                    }
                )
                manual_reasons.append("historical coverage is incomplete")

        missing_metrics = [
            column
            for column in RISK_METRIC_COLUMNS
            if column not in risk or pd.isna(row.get(column))
        ]
        if missing_metrics:
            alerts.append(
                {
                    "Symbol": symbol,
                    "AlertType": "DATA_WARNING",
                    "AlertLevel": "INFO",
                    "Description": "Missing risk metrics: " + ", ".join(missing_metrics) + ".",
                }
            )
            manual_reasons.append("risk metrics are incomplete")

        if status_column is None:
            alerts.append(
                {
                    "Symbol": symbol,
                    "AlertType": "DATA_WARNING",
                    "AlertLevel": "INFO",
                    "Description": "Risk status is unavailable.",
                }
            )
            manual_reasons.append("risk status is unavailable")
        else:
            status = _text(row[status_column]).upper()
            if status != "PASS":
                alerts.append(
                    {
                        "Symbol": symbol,
                        "AlertType": "DATA_WARNING",
                        "AlertLevel": "INFO",
                        "Description": f"Risk calculation status is {status}.",
                    }
                )
                manual_reasons.append(f"risk status is {status}")

        if manual_reasons:
            alerts.append(
                {
                    "Symbol": symbol,
                    "AlertType": "RESEARCH_WARNING",
                    "AlertLevel": "WATCH",
                    "Description": "Manual review required because "
                    + "; ".join(manual_reasons)
                    + ".",
                }
            )
    return pd.DataFrame(alerts, columns=OUTPUT_COLUMNS)


def generate_risk_alerts(validation_path=None, risk_path=None, output_path=None):
    """Load existing artifacts and save the user-layer risk alerts."""
    validation = _load_csv(
        DEFAULT_VALIDATION_PATH if validation_path is None else Path(validation_path)
    )
    risk = _load_csv(DEFAULT_RISK_PATH if risk_path is None else Path(risk_path))
    alerts = build_risk_alerts(validation, risk)
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    alerts.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
    return {"alerts": alerts, "output_path": str(path)}


def main():
    try:
        result = generate_risk_alerts()
    except (ValueError, TypeError, OSError) as error:
        print(f"Risk alert error: {error}", file=sys.stderr)
        return 1
    print("AI_investing Risk Alerts")
    print(f"Alerts: {len(result['alerts'])}")
    print(f"Output: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
