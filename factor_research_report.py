"""Standardized JSON and HTML presentation for factor research results."""

import html
import json
import sys
from pathlib import Path

import pandas as pd

from config import RESULTS_DIR_PATH, display_path
from factor_composite import validate_factor_weights
from factor_report import generate_factor_report
from factor_validation import HORIZONS


DEFAULT_VALIDATION_PATHS = {
    "validation": RESULTS_DIR_PATH / "scale50_factor_validation.csv",
    "rank_ic": RESULTS_DIR_PATH / "scale50_factor_rank_ic.csv",
    "group_returns": RESULTS_DIR_PATH / "scale50_factor_group_returns.csv",
    "turnover": RESULTS_DIR_PATH / "scale50_factor_turnover.csv",
}
DEFAULT_ROBUSTNESS_PATHS = {
    "robust_stats": RESULTS_DIR_PATH / "scale50_factor_validation_robust_stats.csv",
    "regimes": RESULTS_DIR_PATH / "scale50_factor_validation_regimes.csv",
    "coverage": RESULTS_DIR_PATH / "scale50_factor_validation_coverage.csv",
}
DEFAULT_HTML_PATH = RESULTS_DIR_PATH / "scale50_factor_report.html"
DEFAULT_JSON_PATH = RESULTS_DIR_PATH / "scale50_factor_report.json"
LIMITATIONS = [
    "The current universe may contain survivorship bias.",
    "Transaction costs and market impact are not included.",
    "Factor weights are predefined rather than optimized in this report.",
    "Historical universe membership is simplified.",
    "Historical results do not guarantee future returns.",
]


def _values(series):
    return pd.to_numeric(series, errors="coerce").dropna()


def _statistics(series):
    values = _values(series)
    return {
        "count": int(len(values)),
        "mean": float(values.mean()) if len(values) else None,
        "win_rate": float((values > 0).mean()) if len(values) else None,
        "volatility": float(values.std(ddof=1)) if len(values) >= 2 else None,
    }


def _records(table):
    clean = table.astype(object).where(pd.notna(table), None)
    return clean.to_dict(orient="records")


class FactorResearchReport:
    """Build reproducible report data from saved validation and robustness outputs."""

    def __init__(self, validation_paths=None, robustness_paths=None, *, universe="Scale50"):
        self.validation_paths = dict(
            DEFAULT_VALIDATION_PATHS if validation_paths is None else validation_paths
        )
        self.robustness_paths = dict(
            DEFAULT_ROBUSTNESS_PATHS if robustness_paths is None else robustness_paths
        )
        self.universe = str(universe)
        self.validation_tables = {}
        self.robustness_tables = {}
        self.report = None

    def load_results(self):
        core = generate_factor_report(self.validation_paths, save=False)["summary"]
        self.validation_tables = {
            key: pd.read_csv(path) for key, path in self.validation_paths.items()
        }
        self.robustness_tables = {}
        for key, source in self.robustness_paths.items():
            path = Path(source)
            if not path.is_file():
                raise FileNotFoundError(f"Factor robustness artifact not found: {path}")
            table = pd.read_csv(path)
            if table.empty:
                raise ValueError(f"Factor robustness artifact is empty: {key}")
            self.robustness_tables[key] = table
        return core

    def build_metadata(self, core):
        return {
            "universe": self.universe,
            "period": core["period"],
            "rebalance": "Monthly",
            "holding_periods": [f"{horizon}D" for horizon in HORIZONS],
        }

    def build_factor_summary(self, core):
        weights = validate_factor_weights()["effective_weights"]
        return {
            "name": "Composite Score",
            "components": [
                {"factor": "Trend", "weight": weights["TrendPercentile"]},
                {"factor": "Momentum", "weight": weights["MomentumPercentile"]},
                {"factor": "Low Volatility", "weight": weights["LowVolatilityPercentile"]},
            ],
            "factor_ranking": core["factor_ranking"],
        }

    def build_ic_table(self):
        rank_ic = self.validation_tables["rank_ic"]
        result = []
        for horizon in (f"{value}D" for value in HORIZONS):
            stats = _statistics(rank_ic[rank_ic.Horizon == horizon]["RankIC"])
            result.append({"horizon": horizon, "rank_ic": stats["mean"], **stats})
        return result

    def build_group_analysis(self):
        groups = self.validation_tables["group_returns"]
        result = []
        for horizon in (f"{value}D" for value in HORIZONS):
            subset = groups[groups.Horizon == horizon]
            entry = {"horizon": horizon}
            for label, group in (("top_20", "Top"), ("middle", "Middle"), ("bottom_20", "Bottom")):
                entry[label] = _statistics(
                    subset[subset.Group == group]["AverageForwardReturn"]
                )
            entry["long_short_spread"] = _statistics(
                subset[subset.Group == "Top"]["LongShortSpread"]
            )
            result.append(entry)
        return result

    def build_robustness_summary(self, core):
        stats = self.robustness_tables["robust_stats"]
        regimes = self.robustness_tables["regimes"]
        coverage = self.robustness_tables["coverage"]
        composite_std = core["composite_rank_ic"]["std"]
        return {
            "stability_score": (
                1.0 / (1.0 + composite_std) if composite_std is not None else None
            ),
            "performance_consistency": [
                {
                    "horizon": row.Horizon, "series": row.Series,
                    "positive_ratio": float(row.PositiveRatio) if pd.notna(row.PositiveRatio) else None,
                    "observation_count": int(row.ObservationCount),
                }
                for row in stats.itertuples(index=False)
                if row.Series == "Top-Bottom"
            ],
            "period_or_regime_checks": _records(regimes),
            "minimum_score_coverage": (
                float(pd.to_numeric(coverage.ScoreCoverageRatio, errors="coerce").min())
                if "ScoreCoverageRatio" in coverage else None
            ),
        }

    def build_report(self):
        core = self.load_results()
        turnover = _statistics(self.validation_tables["turnover"]["Turnover"])
        self.report = {
            "metadata": self.build_metadata(core),
            "factor_model": self.build_factor_summary(core),
            "ic_analysis": self.build_ic_table(),
            "group_analysis": self.build_group_analysis(),
            "turnover_analysis": {"monthly_turnover": turnover},
            "robustness_analysis": self.build_robustness_summary(core),
            "limitations": list(LIMITATIONS),
            "conclusion": core["conclusion"],
        }
        return self.report

    def export_json(self, output_path=DEFAULT_JSON_PATH):
        report = self.report if self.report is not None else self.build_report()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        return path

    def export_html(self, output_path=DEFAULT_HTML_PATH):
        report = self.report if self.report is not None else self.build_report()
        metadata = report["metadata"]
        ic_rows = "".join(
            f"<tr><td>{row['horizon']}</td><td>{_format(row['rank_ic'])}</td>"
            f"<td>{_format(row['win_rate'], percent=True)}</td></tr>"
            for row in report["ic_analysis"]
        )
        group_rows = "".join(
            f"<tr><td>{row['horizon']}</td><td>{_format(row['top_20']['mean'], True)}</td>"
            f"<td>{_format(row['middle']['mean'], True)}</td>"
            f"<td>{_format(row['bottom_20']['mean'], True)}</td>"
            f"<td>{_format(row['long_short_spread']['mean'], True)}</td></tr>"
            for row in report["group_analysis"]
        )
        components = "".join(
            f"<li>{html.escape(item['factor'])}: {_format(item['weight'], True)}</li>"
            for item in report["factor_model"]["components"]
        )
        limitations = "".join(f"<li>{html.escape(item)}</li>" for item in report["limitations"])
        content = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>AI_investing Factor Research Report</title><style>body{{font-family:Arial,sans-serif;max-width:1050px;margin:40px auto;color:#172033}}table{{border-collapse:collapse;width:100%;margin:16px 0 28px}}th,td{{border:1px solid #d8dee9;padding:9px;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef2f7}}</style></head><body>
<h1>AI_investing Factor Research Report</h1><h2>Research Metadata</h2>
<p><b>Universe:</b> {html.escape(metadata['universe'])}<br><b>Period:</b> {metadata['period'][0]} to {metadata['period'][1]}<br><b>Rebalance:</b> Monthly<br><b>Holding Period:</b> {' / '.join(metadata['holding_periods'])}</p>
<h2>Factor Model</h2><p>Composite Score</p><ul>{components}</ul>
<h2>Information Coefficient Analysis</h2><table><tr><th>Horizon</th><th>Rank IC</th><th>Positive Ratio</th></tr>{ic_rows}</table>
<p>Positive IC indicates positive ranking association; higher IC indicates stronger historical ranking ability.</p>
<h2>Portfolio Group Analysis</h2><table><tr><th>Horizon</th><th>Top 20%</th><th>Middle</th><th>Bottom 20%</th><th>Spread</th></tr>{group_rows}</table>
<h2>Turnover Analysis</h2><p>Monthly mean turnover: {_format(report['turnover_analysis']['monthly_turnover']['mean'], True)}. Transaction costs are not included.</p>
<h2>Robustness Analysis</h2><p>Stability score: {_format(report['robustness_analysis']['stability_score'])}; minimum score coverage: {_format(report['robustness_analysis']['minimum_score_coverage'], True)}</p>
<h2>Research Limitations</h2><ol>{limitations}</ol><h2>Conclusion</h2><p>{html.escape(report['conclusion'])}</p>
</body></html>"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def generate(self, *, html_path=DEFAULT_HTML_PATH, json_path=DEFAULT_JSON_PATH):
        report = self.build_report()
        return {
            "html_path": str(self.export_html(html_path)),
            "json_path": str(self.export_json(json_path)),
            "report": report,
        }


def _format(value, percent=False):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.2%}" if percent else f"{float(value):.4f}"


def generate_factor_research_report(
    validation_paths=None, robustness_paths=None, *, universe="Scale50",
    html_path=DEFAULT_HTML_PATH, json_path=DEFAULT_JSON_PATH,
):
    return FactorResearchReport(
        validation_paths, robustness_paths, universe=universe
    ).generate(html_path=html_path, json_path=json_path)


def main():
    try:
        result = generate_factor_research_report()
        print("================================")
        print("AI_investing Factor Research Report")
        print("================================")
        print("Universe:")
        print(result["report"]["metadata"]["universe"])
        print("Report generated:")
        print(display_path(result["html_path"]))
        print(display_path(result["json_path"]))
        return 0
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        print(f"Factor research report error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
