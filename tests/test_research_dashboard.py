import json
import tempfile
import unittest
from pathlib import Path

import research_dashboard as dashboard


def report_fixture():
    return {
        "metadata": {
            "universe": "Scale50", "period": ["2024-01-01", "2026-01-01"],
            "rebalance": "Monthly", "holding_periods": ["5D", "10D", "20D", "60D"],
        },
        "factor_model": {
            "name": "Composite Score",
            "components": [
                {"factor": "Trend", "weight": .35},
                {"factor": "Momentum", "weight": .35},
                {"factor": "Low Volatility", "weight": .30},
            ],
            "factor_ranking": [
                {"factor": "Trend", "mean_rank_ic": .1, "ic_std": .2, "rank": 1}
            ],
        },
        "ic_analysis": [
            {"horizon": "5D", "rank_ic": .1, "volatility": .2, "win_rate": .6},
            {"horizon": "10D", "rank_ic": -.1, "volatility": .3, "win_rate": .4},
        ],
        "group_analysis": [{
            "horizon": "5D", "top_20": {"mean": .02, "volatility": .1, "win_rate": .6},
            "middle": {"mean": .01, "volatility": .08, "win_rate": .55},
            "bottom_20": {"mean": 0, "volatility": .09, "win_rate": .5},
            "long_short_spread": {"mean": .02, "volatility": .12, "win_rate": .6},
        }],
        "turnover_analysis": {"monthly_turnover": {"mean": .25}},
        "robustness_analysis": {
            "stability_score": .75, "minimum_score_coverage": 1.0,
            "performance_consistency": [{"horizon": "5D", "positive_ratio": .6, "observation_count": 20}],
            "period_or_regime_checks": [{"Regime": "RiskOn", "MeanRankIC": .1}],
        },
        "limitations": ["Historical results do not guarantee future returns."],
        "conclusion": "Original <research> conclusion.",
    }


class ResearchDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_report(self, value=None):
        path = self.root / "report.json"
        path.write_text(json.dumps(report_fixture() if value is None else value), encoding="utf-8")
        return path

    def test_json_loading(self):
        self.assertEqual(dashboard.load_research_report(self.write_report())["metadata"]["universe"], "Scale50")

    def test_missing_file_handling(self):
        with self.assertRaises(FileNotFoundError):
            dashboard.load_research_report(self.root / "missing.json")

    def test_invalid_json_handling(self):
        path = self.root / "bad.json"; path.write_text("{bad", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid"):
            dashboard.load_research_report(path)

    def test_non_object_root_handling(self):
        with self.assertRaisesRegex(ValueError, "root"):
            dashboard.load_research_report(self.write_report([]))

    def test_invalid_structure_handling(self):
        value = report_fixture(); value.pop("conclusion")
        with self.assertRaisesRegex(ValueError, "missing required"):
            dashboard.load_research_report(self.write_report(value))

    def test_incorrect_section_type(self):
        value = report_fixture(); value["ic_analysis"] = {}
        with self.assertRaisesRegex(ValueError, "incorrect types"):
            dashboard.load_research_report(self.write_report(value))

    def test_dashboard_data_parsing(self):
        data = dashboard.build_dashboard_data(report_fixture())
        self.assertEqual(data["ic_analysis"]["best_horizon"], "5D")
        self.assertEqual(data["ic_analysis"]["weakest_horizon"], "10D")

    def test_conclusion_preservation(self):
        data = dashboard.build_dashboard_data(report_fixture())
        self.assertEqual(data["conclusion"], "Original <research> conclusion.")

    def test_html_generation_escapes_content(self):
        rendered = dashboard.render_dashboard_html(dashboard.build_dashboard_data(report_fixture()))
        self.assertIn("Original &lt;research&gt; conclusion.", rendered)
        self.assertNotIn("Original <research>", rendered)

    def test_output_file_creation(self):
        output = self.root / "dashboard.html"
        result = dashboard.generate_research_dashboard(self.write_report(), output)
        self.assertEqual(result, output)
        self.assertTrue(output.is_file())

    def test_deterministic_rendering(self):
        data = dashboard.build_dashboard_data(report_fixture())
        self.assertEqual(dashboard.render_dashboard_html(data), dashboard.render_dashboard_html(data))

    def test_missing_metrics_display_not_available(self):
        data = dashboard.build_dashboard_data(report_fixture())
        self.assertEqual(data["overview"]["symbol_count"], dashboard.NOT_AVAILABLE_CANONICAL)
        rendered = dashboard.render_dashboard_html(data)
        self.assertIn("Not available", rendered)

    def test_no_forbidden_engine_imports(self):
        source = Path(dashboard.__file__).read_text(encoding="utf-8")
        for name in ("factor_validation", "factor_composite", "price_factors", "portfolio", "backtest"):
            self.assertNotIn(f"import {name}", source)


if __name__ == "__main__":
    unittest.main()
