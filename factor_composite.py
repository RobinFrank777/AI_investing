"""Research-only composite baseline for normalized native factors."""

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from config import RESULTS_DIR_PATH, display_path
from factor_normalization import build_normalized_factor_table


FACTOR_COMPOSITE_OUTPUT_PATH = RESULTS_DIR_PATH / "factor_composite.csv"
WEIGHT_SUM_TOLERANCE = 1e-9
HIGH_CORRELATION_THRESHOLD = 0.80
MIN_COMPLETE_SAMPLE = 5
HIGH_MISSING_SCORE_RATIO = 0.50

DEFAULT_STRENGTH_WEIGHTS = {
    "TrendPercentile": 0.50,
    "MomentumPercentile": 0.50,
}
DEFAULT_GROUP_WEIGHTS = {
    "StrengthScore": 0.70,
    "RiskQualityScore": 0.30,
}
COMPOSITE_COLUMNS = [
    "Ticker", "AsOfDate", "NormalizationStatus",
    "TrendPercentile", "MomentumPercentile", "LowVolatilityPercentile",
    "StrengthScore", "RiskQualityScore", "TrendContribution",
    "MomentumContribution", "LowVolatilityContribution",
    "CompositeFactorScore", "CompositeRank", "CompositePercentile",
    "CompositeStatus", "CompositeMissingFactors", "CompositeMessage",
]


def _validate_weights(weights, defaults, name):
    supplied = defaults if weights is None else weights
    if not isinstance(supplied, dict):
        raise ValueError(f"{name} weights must be a dictionary")
    expected = set(defaults)
    actual = set(supplied)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise ValueError(f"{name} weights are missing keys: {missing}")
    if extra:
        raise ValueError(f"{name} weights contain unsupported keys: {extra}")
    result = {}
    for key in defaults:
        value = supplied[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} weight {key} must be numeric")
        if not math.isfinite(value):
            raise ValueError(f"{name} weight {key} must be finite")
        if value < 0:
            raise ValueError(f"{name} weight {key} must be nonnegative")
        result[key] = float(value)
    total = sum(result.values())
    if total <= 0:
        raise ValueError(f"{name} weights must contain a positive value")
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=WEIGHT_SUM_TOLERANCE):
        raise ValueError(f"{name} weights must sum to 1.0; received {total}")
    return result


def validate_factor_weights(strength_weights=None, group_weights=None):
    """Validate weights and return defensive copies plus effective weights."""
    strength = _validate_weights(
        strength_weights, DEFAULT_STRENGTH_WEIGHTS, "strength"
    )
    groups = _validate_weights(group_weights, DEFAULT_GROUP_WEIGHTS, "group")
    effective = {
        "TrendPercentile": strength["TrendPercentile"] * groups["StrengthScore"],
        "MomentumPercentile": strength["MomentumPercentile"] * groups["StrengthScore"],
        "LowVolatilityPercentile": groups["RiskQualityScore"],
    }
    return {
        "strength_weights": strength,
        "group_weights": groups,
        "effective_weights": effective,
    }


def _finite(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def calculate_composite_row(
    row, *, strength_weights=None, group_weights=None, missing_policy="strict"
):
    """Calculate one strict-policy composite row without cross-sectional ranking."""
    if missing_policy != "strict":
        raise ValueError("unsupported missing policy: " + str(missing_policy))
    weights = validate_factor_weights(strength_weights, group_weights)
    values = {
        name: _finite(row.get(name))
        for name in (
            "TrendPercentile", "MomentumPercentile", "LowVolatilityPercentile"
        )
    }
    missing = [name for name, value in values.items() if value is None]
    available = len(values) - len(missing)
    result = {
        "StrengthScore": None, "RiskQualityScore": values["LowVolatilityPercentile"],
        "TrendContribution": None, "MomentumContribution": None,
        "LowVolatilityContribution": None, "CompositeFactorScore": None,
        "CompositeRank": None, "CompositePercentile": None,
        "CompositeStatus": "FAILED" if available == 0 else "PARTIAL",
        "CompositeMissingFactors": ";".join(missing),
        "CompositeMessage": (
            "No normalized factors available" if available == 0
            else "Strict policy requires all factors"
        ),
    }
    if values["TrendPercentile"] is not None and values["MomentumPercentile"] is not None:
        result["StrengthScore"] = (
            values["TrendPercentile"] * weights["strength_weights"]["TrendPercentile"]
            + values["MomentumPercentile"] * weights["strength_weights"]["MomentumPercentile"]
        )
    if missing:
        return result

    effective = weights["effective_weights"]
    result["TrendContribution"] = values["TrendPercentile"] * effective["TrendPercentile"]
    result["MomentumContribution"] = values["MomentumPercentile"] * effective["MomentumPercentile"]
    result["LowVolatilityContribution"] = values["LowVolatilityPercentile"] * effective["LowVolatilityPercentile"]
    result["CompositeFactorScore"] = sum(
        result[name] for name in (
            "TrendContribution", "MomentumContribution", "LowVolatilityContribution"
        )
    )
    result.update({
        "CompositeStatus": "PASS", "CompositeMissingFactors": "",
        "CompositeMessage": "",
    })
    return result


def build_composite_factor_table(
    normalized=None, *, strength_weights=None, group_weights=None,
    missing_policy="strict"
):
    """Build the composite table in original Universe order."""
    source = build_normalized_factor_table() if normalized is None else normalized.copy(deep=True)
    if not isinstance(source, pd.DataFrame):
        raise ValueError("normalized input must be a pandas DataFrame")
    required = [
        "Ticker", "AsOfDate", "TrendPercentile", "MomentumPercentile",
        "LowVolatilityPercentile",
    ]
    missing = [column for column in required if column not in source]
    if missing:
        raise ValueError("normalized input is missing columns: " + ", ".join(missing))
    validate_factor_weights(strength_weights, group_weights)
    rows = []
    for _, source_row in source.iterrows():
        result = {
            "Ticker": source_row["Ticker"], "AsOfDate": source_row["AsOfDate"],
            "NormalizationStatus": source_row.get("NormalizationStatus"),
            "TrendPercentile": _finite(source_row["TrendPercentile"]),
            "MomentumPercentile": _finite(source_row["MomentumPercentile"]),
            "LowVolatilityPercentile": _finite(source_row["LowVolatilityPercentile"]),
        }
        result.update(calculate_composite_row(
            source_row, strength_weights=strength_weights,
            group_weights=group_weights, missing_policy=missing_policy,
        ))
        rows.append(result)
    table = pd.DataFrame(rows, columns=COMPOSITE_COLUMNS)
    valid = pd.to_numeric(table["CompositeFactorScore"], errors="coerce")
    table["CompositeRank"] = valid.rank(method="average", ascending=False)
    table["CompositePercentile"] = valid.rank(method="average", pct=True)
    dates = sorted({str(value) for value in table["AsOfDate"] if pd.notna(value)})
    if len(dates) > 1:
        inherited = "Mixed AsOfDate values inherited from normalization"
        table["CompositeMessage"] = table["CompositeMessage"].map(
            lambda value: "; ".join(filter(None, [value, inherited]))
        )
    return table[COMPOSITE_COLUMNS]


def build_composite_ranking(composite=None):
    """Return a stable descending research ranking without mutating its source."""
    table = build_composite_factor_table() if composite is None else composite.copy(deep=True)
    if "CompositeFactorScore" not in table:
        raise ValueError("composite input requires CompositeFactorScore")
    table["CompositeRank"] = pd.to_numeric(
        table["CompositeFactorScore"], errors="coerce"
    ).rank(method="average", ascending=False)
    valid = pd.to_numeric(table["CompositeFactorScore"], errors="coerce")
    table["CompositePercentile"] = valid.rank(method="average", pct=True)
    table["_OriginalOrder"] = range(len(table))
    ranked = table.sort_values(
        ["CompositeFactorScore", "_OriginalOrder"],
        ascending=[False, True], na_position="last", kind="mergesort",
    )
    return ranked.drop(columns="_OriginalOrder").reset_index(drop=True)


def build_composite_diagnostics(composite, strength_weights=None, group_weights=None):
    """Return score distribution, redundancy diagnostics, and stable warnings."""
    if not isinstance(composite, pd.DataFrame):
        raise ValueError("composite must be a pandas DataFrame")
    weights = validate_factor_weights(strength_weights, group_weights)
    scores = pd.to_numeric(composite["CompositeFactorScore"], errors="coerce")
    finite = scores[scores.map(lambda value: pd.notna(value) and math.isfinite(value))]
    count = len(composite)
    complete = len(finite)
    correlation = None
    if {"TrendPercentile", "MomentumPercentile"}.issubset(composite.columns):
        pair = composite[["TrendPercentile", "MomentumPercentile"]].apply(
            pd.to_numeric, errors="coerce"
        ).dropna()
        if len(pair) >= 2:
            value = pair.corr().iloc[0, 1]
            correlation = float(value) if pd.notna(value) else None
    warnings = []
    if correlation is not None and abs(correlation) >= HIGH_CORRELATION_THRESHOLD:
        warnings.append("High Trend/Momentum correlation")
    if complete < MIN_COMPLETE_SAMPLE:
        warnings.append(f"Small complete sample ({complete})")
    if complete >= 2 and finite.nunique() == 1:
        warnings.append("Constant CompositeFactorScore")
    if count and (count - complete) / count >= HIGH_MISSING_SCORE_RATIO:
        warnings.append(f"High missing score ratio ({count - complete}/{count})")
    dates = sorted({str(value) for value in composite.get("AsOfDate", []) if pd.notna(value)})
    if len(dates) > 1:
        warnings.append("Mixed AsOfDate values")
    std = finite.std(ddof=1) if complete >= 2 else None
    return {
        "row_count": int(count), "complete_score_count": int(complete),
        "missing_score_count": int(count - complete),
        "score_min": float(finite.min()) if complete else None,
        "score_max": float(finite.max()) if complete else None,
        "score_mean": float(finite.mean()) if complete else None,
        "score_std": float(std) if std is not None and pd.notna(std) else None,
        "unique_score_count": int(finite.nunique()),
        "effective_weights": weights["effective_weights"],
        "component_correlations": {"TrendMomentum": correlation},
        "warnings": warnings,
    }


SENSITIVITY_SCHEMES = {
    "Baseline": (DEFAULT_STRENGTH_WEIGHTS, DEFAULT_GROUP_WEIGHTS),
    "Equal Factor": (
        DEFAULT_STRENGTH_WEIGHTS,
        {"StrengthScore": 2 / 3, "RiskQualityScore": 1 / 3},
    ),
    "Strength Focus": (
        DEFAULT_STRENGTH_WEIGHTS,
        {"StrengthScore": 0.80, "RiskQualityScore": 0.20},
    ),
    "Risk Balanced": (
        DEFAULT_STRENGTH_WEIGHTS,
        {"StrengthScore": 0.60, "RiskQualityScore": 0.40},
    ),
}


def build_weight_sensitivity(normalized, top_n=5):
    """Compare four transparent schemes without selecting or optimizing one."""
    rankings = {}
    for name, (strength, groups) in SENSITIVITY_SCHEMES.items():
        table = build_composite_factor_table(
            normalized, strength_weights=strength, group_weights=groups
        )
        rankings[name] = build_composite_ranking(table)
    baseline = rankings["Baseline"]
    baseline_top = baseline["Ticker"].head(top_n).tolist()
    baseline_ranks = baseline.set_index("Ticker")["CompositeRank"]
    result = {}
    for name, ranking in rankings.items():
        top = ranking["Ticker"].head(top_n).tolist()
        current = ranking.set_index("Ticker")["CompositeRank"]
        aligned = pd.concat([baseline_ranks, current], axis=1).dropna()
        rank_change = (aligned.iloc[:, 0] - aligned.iloc[:, 1]).abs()
        correlation = aligned.iloc[:, 0].rank(method="average").corr(
            aligned.iloc[:, 1].rank(method="average")
        )
        result[name] = {
            "top_symbols": top,
            "top_overlap_count": int(len(set(top) & set(baseline_top))),
            "spearman_with_baseline": float(correlation),
            "largest_rank_change": float(rank_change.max()) if len(rank_change) else None,
        }
    return result


def save_composite_factor_table(
    normalized=None, output_path=None, *, strength_weights=None,
    group_weights=None, missing_policy="strict"
):
    path = FACTOR_COMPOSITE_OUTPUT_PATH if output_path is None else Path(output_path)
    table = build_composite_factor_table(
        normalized, strength_weights=strength_weights,
        group_weights=group_weights, missing_policy=missing_policy,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, encoding="utf-8")
    return path


def _parser():
    parser = argparse.ArgumentParser(description="Build Composite Factor baseline")
    parser.add_argument("--input", type=Path, help="Normalized factor CSV")
    parser.add_argument("--output", type=Path, help="Composite CSV output path")
    return parser


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
        normalized = pd.read_csv(args.input) if args.input else build_normalized_factor_table()
        path = save_composite_factor_table(normalized, args.output)
        table = pd.read_csv(path)
        counts = table["CompositeStatus"].value_counts()
        weights = validate_factor_weights()["effective_weights"]
        print("Composite Factor Baseline")
        print(f"Rows: {len(table)}")
        for status in ("PASS", "PARTIAL", "FAILED"):
            print(f"{status}: {int(counts.get(status, 0))}")
        print("Missing Policy: strict\n")
        print("Default Effective Weights")
        print(f"Trend: {weights['TrendPercentile']:.2f}")
        print(f"Momentum: {weights['MomentumPercentile']:.2f}")
        print(f"Low Volatility: {weights['LowVolatilityPercentile']:.2f}")
        print(f"\nOutput: {display_path(path)}")
        return 0
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        print(f"Composite Factor error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
