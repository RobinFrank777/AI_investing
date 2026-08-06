"""Human-readable reporting for existing factor-validation artifacts."""

import html
import math
from pathlib import Path

import pandas as pd

from config import RESULTS_DIR_PATH
from factor_validation import (
    HORIZONS, build_group_return_table, build_rank_ic_table,
    build_turnover_table,
)


DEFAULT_SCORE_WEIGHTS = {"ic": 0.40, "return": 0.40, "stability": 0.20}
FACTOR_COLUMNS = {
    "Trend": "TrendPercentile",
    "Momentum": "MomentumPercentile",
    "Low Volatility": "LowVolatilityPercentile",
}
PATH_KEYS = ("validation", "rank_ic", "group_returns", "turnover")
REQUIRED_COLUMNS = {
    "validation": {
        "RebalanceDate", "Ticker", *FACTOR_COLUMNS.values(),
        *(f"ForwardReturn{horizon}D" for horizon in HORIZONS),
    },
    "rank_ic": {"RebalanceDate", "Horizon", "ValidPairs", "RankIC"},
    "group_returns": {
        "RebalanceDate", "Horizon", "Group", "AverageForwardReturn",
        "LongShortSpread",
    },
    "turnover": {"CurrentDate", "Turnover"},
}


def _load_tables(validation_paths):
    if not isinstance(validation_paths, dict):
        raise ValueError("validation_paths must be a dictionary")
    missing_paths = [key for key in PATH_KEYS if key not in validation_paths]
    if missing_paths:
        raise ValueError("Missing validation paths: " + ", ".join(missing_paths))
    tables = {}
    for key in PATH_KEYS:
        path = Path(validation_paths[key])
        if not path.is_file():
            raise FileNotFoundError(f"Factor validation artifact not found: {path}")
        table = pd.read_csv(path)
        if table.empty:
            raise ValueError(f"Factor validation artifact is empty: {key}")
        missing = sorted(REQUIRED_COLUMNS[key] - set(table.columns))
        if missing:
            raise ValueError(f"{key} is missing required columns: {', '.join(missing)}")
        tables[key] = table
    return tables


def _weights(score_weights):
    weights = dict(DEFAULT_SCORE_WEIGHTS if score_weights is None else score_weights)
    if set(weights) != set(DEFAULT_SCORE_WEIGHTS):
        raise ValueError("score_weights must contain ic, return, and stability")
    try:
        weights = {key: float(value) for key, value in weights.items()}
    except (TypeError, ValueError) as error:
        raise ValueError("score weights must be numeric") from error
    if any(not math.isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("score weights must be finite and nonnegative")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("score weights must sum to 1")
    return weights


def _clean(series):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return values[values.map(math.isfinite)]


def _mean(series):
    values = _clean(series)
    return float(values.mean()) if len(values) else None


def _factor_statistics(validation):
    factors = []
    for factor, column in FACTOR_COLUMNS.items():
        proxy = validation.copy(deep=True)
        proxy["CompositeFactorScore"] = pd.to_numeric(proxy[column], errors="coerce")
        rank_ic = build_rank_ic_table(proxy)
        groups = build_group_return_table(proxy)
        turnover = build_turnover_table(proxy)
        ic_values = _clean(rank_ic["RankIC"])
        ic_std = float(ic_values.std(ddof=1)) if len(ic_values) >= 2 else None
        factors.append({
            "factor": factor,
            "mean_rank_ic": float(ic_values.mean()) if len(ic_values) else None,
            "ic_std": ic_std,
            "positive_ic_ratio": float((ic_values > 0).mean()) if len(ic_values) else None,
            "ic_stability": 1.0 / (1.0 + ic_std) if ic_std is not None else None,
            "average_top_return": _mean(groups[groups.Group == "Top"]["AverageForwardReturn"]),
            "average_long_short_spread": _mean(groups[groups.Group == "Top"]["LongShortSpread"]),
            "average_turnover": _mean(turnover["Turnover"]),
        })
    return factors


def _normalized(values, *, higher=True):
    clean = [value for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return [0.0] * len(values)
    low, high = min(clean), max(clean)
    if math.isclose(low, high, abs_tol=1e-15):
        return [0.5 if value is not None else 0.0 for value in values]
    scores = []
    for value in values:
        if value is None or not math.isfinite(value):
            scores.append(0.0)
            continue
        score = (value - low) / (high - low)
        scores.append(float(score if higher else 1.0 - score))
    return scores


def _rank_factors(factors, weights):
    ic_scores = _normalized([row["mean_rank_ic"] for row in factors])
    return_scores = _normalized([row["average_long_short_spread"] for row in factors])
    stability_scores = _normalized([row["ic_stability"] for row in factors])
    for row, ic_score, return_score, stability_score in zip(
        factors, ic_scores, return_scores, stability_scores
    ):
        row.update({
            "ic_score": ic_score, "return_score": return_score,
            "stability_score": stability_score,
            "score": (
                ic_score * weights["ic"]
                + return_score * weights["return"]
                + stability_score * weights["stability"]
            ),
        })
    ordered = sorted(factors, key=lambda row: (-row["score"], row["factor"]))
    for rank, row in enumerate(ordered, start=1):
        row["rank"] = rank
    return ordered


def _group_summary(groups):
    result = {}
    for horizon in (f"{value}D" for value in HORIZONS):
        subset = groups[groups.Horizon == horizon]
        result[horizon] = {
            "top_return": _mean(subset[subset.Group == "Top"]["AverageForwardReturn"]),
            "bottom_return": _mean(subset[subset.Group == "Bottom"]["AverageForwardReturn"]),
            "long_short_spread": _mean(subset[subset.Group == "Top"]["LongShortSpread"]),
        }
    return result


def _conclusion(ranking):
    leader = ranking[0]
    ic = leader["mean_rank_ic"]
    spread = leader["average_long_short_spread"]
    if ic is not None and spread is not None and ic > 0 and spread > 0:
        evidence = "shows positive IC and long-short spread evidence"
    elif (ic is not None and ic > 0) or (spread is not None and spread > 0):
        evidence = "shows mixed validation evidence"
    else:
        evidence = "does not show positive validation evidence"
    return (
        f"{leader['factor']} ranks first under the configured research score and {evidence}. "
        "This diagnostic does not constitute an investment recommendation or production approval."
    )


def _fmt(value, percent=False):
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value:.2%}" if percent else f"{value:.4f}"


def _render_html(summary, title):
    factor_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in (
            row["factor"], _fmt(row["mean_rank_ic"]), _fmt(row["ic_stability"]),
            _fmt(row["average_top_return"], True), _fmt(row["average_turnover"], True),
            str(row["rank"]), _fmt(row["score"]),
        )) + "</tr>" for row in summary["factor_ranking"]
    )
    ic_rows = "".join(
        f"<tr><td>{html.escape(row['factor'])}</td><td>{_fmt(row['mean_rank_ic'])}</td>"
        f"<td>{_fmt(row['ic_std'])}</td><td>{_fmt(row['positive_ic_ratio'], True)}</td></tr>"
        for row in summary["factor_ranking"]
    )
    group_rows = "".join(
        f"<tr><td>{horizon}</td><td>{_fmt(values['top_return'], True)}</td>"
        f"<td>{_fmt(values['bottom_return'], True)}</td>"
        f"<td>{_fmt(values['long_short_spread'], True)}</td></tr>"
        for horizon, values in summary["portfolio_groups"].items()
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;color:#172033}}table{{border-collapse:collapse;width:100%;margin:16px 0 28px}}th,td{{border:1px solid #d8dee9;padding:9px;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef2f7}}.meta{{background:#f7f9fc;padding:16px}}small{{color:#586174}}</style></head>
<body><h1>{html.escape(title)}</h1><div class="meta"><b>Universe:</b> {html.escape(summary['universe'])}<br>
<b>Period:</b> {html.escape(summary['period'][0])} to {html.escape(summary['period'][1])}<br>
<b>Rebalance:</b> Monthly<br><b>Horizons:</b> {' / '.join(summary['horizons'])}</div>
<h2>Factor Performance Summary</h2><table><tr><th>Factor</th><th>Mean Rank IC</th><th>IC Stability</th><th>Avg Top Return</th><th>Turnover</th><th>Rank</th><th>Score</th></tr>{factor_rows}</table>
<h2>Rank IC Analysis</h2><table><tr><th>Factor</th><th>Mean IC</th><th>IC Std</th><th>Positive IC Ratio</th></tr>{ic_rows}</table>
<h2>Portfolio Group Analysis</h2><table><tr><th>Horizon</th><th>Top 20%</th><th>Bottom 20%</th><th>Long-Short</th></tr>{group_rows}</table>
<h2>Research Conclusion</h2><p>{html.escape(summary['conclusion'])}</p>
<small>Research diagnostics only. Historical results do not prove future performance. No brokerage order is created by this report.</small></body></html>"""


def generate_factor_report(
    validation_paths, *, output_path=None, title=None, save=True,
    score_weights=None,
):
    """Load validation artifacts and return a deterministic research report summary."""
    tables = _load_tables(validation_paths)
    weights = _weights(score_weights)
    source_names = [Path(validation_paths[key]).name for key in PATH_KEYS]
    scale50 = any(name.startswith("scale50_") for name in source_names)
    universe = "Scale50" if scale50 else "Production"
    dates = pd.to_datetime(tables["validation"]["RebalanceDate"], errors="coerce").dropna()
    if dates.empty:
        raise ValueError("validation contains no usable RebalanceDate values")
    factors = _rank_factors(_factor_statistics(tables["validation"]), weights)
    summary = {
        "universe": universe,
        "period": [dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")],
        "rebalance": "Monthly",
        "horizons": [f"{value}D" for value in HORIZONS],
        "factor_ranking": factors,
        "composite_rank_ic": {
            "mean": _mean(tables["rank_ic"]["RankIC"]),
            "std": (
                float(_clean(tables["rank_ic"]["RankIC"]).std(ddof=1))
                if len(_clean(tables["rank_ic"]["RankIC"])) >= 2 else None
            ),
        },
        "portfolio_groups": _group_summary(tables["group_returns"]),
        "composite_turnover": _mean(tables["turnover"]["Turnover"]),
        "score_weights": weights,
    }
    summary["conclusion"] = _conclusion(factors)
    path = Path(output_path) if output_path is not None else RESULTS_DIR_PATH / (
        "scale50_factor_report.html" if scale50 else "factor_report.html"
    )
    if save:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _render_html(summary, title or "AI_investing Factor Research Report"),
            encoding="utf-8",
        )
    return {"report_path": str(path) if save else None, "summary": summary}
