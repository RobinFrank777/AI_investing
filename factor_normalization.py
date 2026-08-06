"""Deterministic cross-sectional normalization for native price factors."""

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from config import RESULTS_DIR_PATH, display_path
from factor_snapshot import build_factor_snapshot_table


FACTOR_NORMALIZED_OUTPUT_PATH = RESULTS_DIR_PATH / "factor_normalized.csv"
MIN_NORMALIZATION_SAMPLE = 2
HIGH_MISSING_RATIO = 0.50

FACTOR_SPECS = (
    ("TrendValue", "TrendPercentile", True),
    ("MomentumValue", "MomentumPercentile", True),
    ("Volatility20D", "LowVolatilityPercentile", False),
)
NORMALIZED_COLUMNS = [
    "Ticker", "AsOfDate", "FactorStatus",
    "TrendValue", "TrendPercentile",
    "MomentumValue", "MomentumPercentile",
    "Volatility20D", "LowVolatilityPercentile",
    "NormalizationStatus", "NormalizationMissingFactors",
    "NormalizationMessage",
]


def _finite_values(values):
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.where(numeric.map(lambda value: pd.isna(value) or math.isfinite(value)))


def normalize_factor_series(values, *, higher_is_better=True, method="percentile"):
    """Return average-tie percentile ranks, preserving index and missing values."""
    if not isinstance(values, pd.Series):
        raise ValueError("normalization input must be a pandas Series")
    if method != "percentile":
        raise ValueError("unsupported normalization method: " + str(method))
    clean = _finite_values(values.copy(deep=True))
    if clean.notna().sum() < MIN_NORMALIZATION_SAMPLE:
        return pd.Series(float("nan"), index=values.index, dtype=float)
    return clean.rank(method="average", pct=True, ascending=higher_is_better)


def _dates(snapshot):
    if "AsOfDate" not in snapshot:
        return []
    return sorted({str(value) for value in snapshot["AsOfDate"] if pd.notna(value) and str(value)})


def build_normalized_factor_table(snapshot=None):
    """Normalize each factor across its finite sample without sorting rows."""
    source = build_factor_snapshot_table() if snapshot is None else snapshot.copy(deep=True)
    if not isinstance(source, pd.DataFrame):
        raise ValueError("snapshot must be a pandas DataFrame")
    required = ["Ticker", "AsOfDate"] + [spec[0] for spec in FACTOR_SPECS]
    missing = [column for column in required if column not in source]
    if missing:
        raise ValueError("snapshot is missing required columns: " + ", ".join(missing))

    result = pd.DataFrame(index=source.index)
    result["Ticker"] = source["Ticker"]
    result["AsOfDate"] = source["AsOfDate"]
    result["FactorStatus"] = source["FactorStatus"] if "FactorStatus" in source else None
    for raw, percentile, higher_is_better in FACTOR_SPECS:
        result[raw] = _finite_values(source[raw])
        result[percentile] = normalize_factor_series(
            source[raw], higher_is_better=higher_is_better
        )

    native_columns = [spec[0] for spec in FACTOR_SPECS]
    percentile_columns = [spec[1] for spec in FACTOR_SPECS]
    statuses = []
    missing_strings = []
    for index in result.index:
        missing_factors = [
            raw for raw, percentile, _ in FACTOR_SPECS
            if pd.isna(result.at[index, raw]) or pd.isna(result.at[index, percentile])
        ]
        available = sum(pd.notna(result.at[index, column]) for column in percentile_columns)
        statuses.append("PASS" if available == 3 else "PARTIAL" if available else "FAILED")
        missing_strings.append(";".join(missing_factors))
    result["NormalizationStatus"] = statuses
    result["NormalizationMissingFactors"] = missing_strings
    mixed = len(_dates(source)) > 1
    result["NormalizationMessage"] = "Mixed AsOfDate values" if mixed else ""
    return result[NORMALIZED_COLUMNS]


def build_factor_diagnostics(snapshot):
    """Return stable ordinary-Python sample diagnostics and warnings."""
    if not isinstance(snapshot, pd.DataFrame):
        raise ValueError("snapshot must be a pandas DataFrame")
    dates = _dates(snapshot)
    warnings = []
    if len(dates) > 1:
        warnings.append("Mixed AsOfDate values")
    factors = {}
    row_count = len(snapshot)
    for raw, _, _ in FACTOR_SPECS:
        if raw not in snapshot:
            raise ValueError(f"snapshot is missing required column: {raw}")
        clean = _finite_values(snapshot[raw]).dropna()
        valid_count = int(len(clean))
        missing_count = int(row_count - valid_count)
        std = clean.std(ddof=1) if valid_count >= 2 else None
        factors[raw] = {
            "valid_count": valid_count,
            "missing_count": missing_count,
            "min": float(clean.min()) if valid_count else None,
            "max": float(clean.max()) if valid_count else None,
            "mean": float(clean.mean()) if valid_count else None,
            "std": float(std) if std is not None and pd.notna(std) else None,
            "unique_count": int(clean.nunique()),
        }
        if valid_count < MIN_NORMALIZATION_SAMPLE:
            warnings.append(f"Small normalization sample: {raw} ({valid_count})")
        if valid_count >= MIN_NORMALIZATION_SAMPLE and clean.nunique() == 1:
            warnings.append(f"Constant factor values: {raw}")
        if row_count and missing_count / row_count >= HIGH_MISSING_RATIO:
            warnings.append(f"High missing ratio: {raw} ({missing_count}/{row_count})")
    return {
        "row_count": int(row_count), "as_of_dates": dates,
        "mixed_as_of_dates": len(dates) > 1, "factors": factors,
        "warnings": warnings,
    }


def save_normalized_factor_table(snapshot=None, output_path=None):
    path = FACTOR_NORMALIZED_OUTPUT_PATH if output_path is None else Path(output_path)
    table = build_normalized_factor_table(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, encoding="utf-8")
    return path


def _parser():
    parser = argparse.ArgumentParser(description="Normalize native price factors")
    parser.add_argument("--input", type=Path, help="Existing Factor Snapshot CSV")
    parser.add_argument("--output", type=Path, help="Normalized CSV output path")
    return parser


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
        snapshot = pd.read_csv(args.input) if args.input else build_factor_snapshot_table()
        diagnostics = build_factor_diagnostics(snapshot)
        path = save_normalized_factor_table(snapshot, args.output)
        table = pd.read_csv(path)
        counts = table["NormalizationStatus"].value_counts()
        print("Factor Normalization")
        print(f"Rows: {len(table)}")
        for status in ("PASS", "PARTIAL", "FAILED"):
            print(f"{status}: {int(counts.get(status, 0))}")
        dates = diagnostics["as_of_dates"]
        print("As Of Date: " + (dates[0] if len(dates) == 1 else ", ".join(dates)))
        print("\nValid Samples")
        for raw, _, _ in FACTOR_SPECS:
            print(f"{raw}: {diagnostics['factors'][raw]['valid_count']}")
        print(f"\nOutput: {display_path(path)}")
        return 0
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        print(f"Factor Normalization error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
