"""Validate the quality contract of the Universe150 raw research dataset."""

import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_raw.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "universe150_research_validation.csv"
OUTPUT_COLUMNS = ("CheckItem", "Value", "Status")
REQUIRED_COLUMNS = (
    "Ticker",
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
    "FactorStatus",
    "FactorError",
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
    "ObservationCount",
    "RiskStatus",
    "ResearchStatus",
)
METRIC_COLUMNS = (
    "TrendValue",
    "MomentumValue",
    "Volatility20D",
    "AnnualizedVolatility",
    "MaxDrawdown",
    "SharpeRatio",
    "ObservationCount",
)
STATUS_COLUMNS = ("FactorStatus", "RiskStatus", "ResearchStatus")
ALLOWED_STATUSES = frozenset({"PASS", "PARTIAL", "FAILED"})


def _row(item, value, status):
    return {"CheckItem": item, "Value": value, "Status": status}


def _empty_result(overall_status, *, readable, missing_columns=""):
    rows = [
        _row("FileReadable", readable, "PASS" if readable else "FAILED"),
        _row("TotalRows", 0, "PARTIAL" if readable else "FAILED"),
        _row("UniqueTickers", 0, "PARTIAL" if readable else "FAILED"),
        _row("DuplicateTickers", 0, "PASS" if readable else "FAILED"),
        _row(
            "MissingRequiredColumns",
            missing_columns,
            "FAILED" if missing_columns or not readable else "PASS",
        ),
        _row("MissingTickerCount", 0, "PASS" if readable else "FAILED"),
        _row("ResearchPASSCount", 0, "PARTIAL" if readable else "FAILED"),
        _row("ResearchPARTIALCount", 0, "PASS" if readable else "FAILED"),
        _row("ResearchFAILEDCount", 0, "PASS" if readable else "FAILED"),
        _row("InvalidFactorStatusCount", 0, "PASS" if readable else "FAILED"),
        _row("InvalidRiskStatusCount", 0, "PASS" if readable else "FAILED"),
        _row("InvalidResearchStatusCount", 0, "PASS" if readable else "FAILED"),
        _row("MissingMetricValueCount", 0, "PASS" if readable else "FAILED"),
        _row("OverallStatus", overall_status, overall_status),
    ]
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def validate_research_data(data):
    """Return a fixed three-column validation summary for a DataFrame."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("research data must be a pandas DataFrame")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data]
    if missing_columns:
        result = _empty_result(
            "FAILED", readable=True, missing_columns=",".join(missing_columns)
        )
        result.loc[result["CheckItem"] == "TotalRows", "Value"] = len(data)
        return result
    if data.empty:
        return _empty_result("PARTIAL", readable=True)

    ticker = data["Ticker"].fillna("").astype(str).str.strip()
    missing_ticker_count = int(ticker.eq("").sum())
    valid_ticker = ticker[ticker.ne("")]
    duplicate_ticker_count = int(valid_ticker.duplicated(keep="first").sum())
    unique_tickers = int(valid_ticker.nunique())

    normalized_statuses = {}
    invalid_status_counts = {}
    for column in STATUS_COLUMNS:
        values = data[column].fillna("").astype(str).str.strip().str.upper()
        normalized_statuses[column] = values
        invalid_status_counts[column] = int((~values.isin(ALLOWED_STATUSES)).sum())

    research_counts = normalized_statuses["ResearchStatus"].value_counts()
    missing_metric_values = int(data.loc[:, METRIC_COLUMNS].isna().sum().sum())
    has_quality_issue = any(
        (
            missing_ticker_count,
            duplicate_ticker_count,
            missing_metric_values,
            *invalid_status_counts.values(),
        )
    )
    overall_status = "PARTIAL" if has_quality_issue else "PASS"

    rows = [
        _row("FileReadable", True, "PASS"),
        _row("TotalRows", int(len(data)), "PASS"),
        _row("UniqueTickers", unique_tickers, "PASS"),
        _row(
            "DuplicateTickers",
            duplicate_ticker_count,
            "PARTIAL" if duplicate_ticker_count else "PASS",
        ),
        _row("MissingRequiredColumns", "", "PASS"),
        _row(
            "MissingTickerCount",
            missing_ticker_count,
            "PARTIAL" if missing_ticker_count else "PASS",
        ),
        _row("ResearchPASSCount", int(research_counts.get("PASS", 0)), "PASS"),
        _row(
            "ResearchPARTIALCount",
            int(research_counts.get("PARTIAL", 0)),
            "PASS",
        ),
        _row(
            "ResearchFAILEDCount", int(research_counts.get("FAILED", 0)), "PASS"
        ),
    ]
    for column in STATUS_COLUMNS:
        count = invalid_status_counts[column]
        rows.append(
            _row(
                f"Invalid{column}Count", count, "PARTIAL" if count else "PASS"
            )
        )
    rows.extend(
        (
            _row(
                "MissingMetricValueCount",
                missing_metric_values,
                "PARTIAL" if missing_metric_values else "PASS",
            ),
            _row("OverallStatus", overall_status, overall_status),
        )
    )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def validate_research_dataset(input_path=None, output_path=None):
    """Read, validate, and save the Universe150 research validation artifact."""
    input_file = DEFAULT_INPUT_PATH if input_path is None else Path(input_path)
    output_file = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)

    if not input_file.is_file():
        validation = _empty_result("FAILED", readable=False)
    else:
        try:
            data = pd.read_csv(input_file)
        except pd.errors.EmptyDataError:
            validation = _empty_result("PARTIAL", readable=True)
        except (pd.errors.ParserError, UnicodeError, OSError):
            validation = _empty_result("FAILED", readable=False)
        else:
            validation = validate_research_data(data)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    validation.to_csv(output_file, index=False)
    return validation


def main():
    validation = validate_research_dataset()
    overall = validation.loc[
        validation["CheckItem"] == "OverallStatus", "Value"
    ].iloc[0]
    print("AI_investing Universe150 Research Dataset Validation")
    print(f"OverallStatus: {overall}")
    print(f"Output: {DEFAULT_OUTPUT_PATH}")
    return 0 if overall != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
