import json
import tempfile
import unittest
from datetime import datetime as real_datetime, timezone
from pathlib import Path
from unittest.mock import patch

import research_dashboard as dashboard


REQUIRED_TYPES = {
    "metadata": dict,
    "factor_model": dict,
    "ic_analysis": list,
    "group_analysis": list,
    "turnover_analysis": dict,
    "robustness_analysis": dict,
    "limitations": list,
    "conclusion": str,
}


def canonical_report():
    statistics = {"count": 2, "mean": 0.01, "win_rate": 0.5, "volatility": 0.02}
    return {
        "metadata": {
            "universe": "Scale50",
            "period": ["2024-01-31", "2025-12-31"],
            "rebalance": "Monthly",
            "holding_periods": ["5D", "10D", "20D", "60D"],
        },
        "factor_model": {
            "name": "Composite Score",
            "components": [
                {"factor": "Trend", "weight": 0.35},
                {"factor": "Momentum", "weight": 0.35},
                {"factor": "Low Volatility", "weight": 0.30},
            ],
            "factor_ranking": [],
        },
        "ic_analysis": [
            {"horizon": "5D", "rank_ic": 0.03, **statistics},
        ],
        "group_analysis": [
            {
                "horizon": "5D",
                "top_20": dict(statistics),
                "middle": dict(statistics),
                "bottom_20": dict(statistics),
                "long_short_spread": dict(statistics),
            }
        ],
        "turnover_analysis": {"monthly_turnover": dict(statistics)},
        "robustness_analysis": {
            "stability_score": 0.75,
            "performance_consistency": [],
            "period_or_regime_checks": [],
            "minimum_score_coverage": 1.0,
        },
        "limitations": ["Historical results do not guarantee future returns."],
        "conclusion": "Saved research conclusion.",
    }


class ResearchArtifactContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_report(self, report):
        path = self.root / "scale50_factor_report.json"
        path.write_text(
            json.dumps(report, allow_nan=False, sort_keys=True), encoding="utf-8"
        )
        return path

    def test_canonical_json_is_valid_and_has_required_sections(self):
        path = self.write_report(canonical_report())
        loaded = dashboard.load_research_report(path)
        self.assertEqual(set(REQUIRED_TYPES) - set(loaded), set())
        for field, expected_type in REQUIRED_TYPES.items():
            self.assertIsInstance(loaded[field], expected_type)

    def test_each_incorrect_required_section_type_is_rejected(self):
        for field, expected_type in REQUIRED_TYPES.items():
            with self.subTest(field=field, expected_type=expected_type):
                report = canonical_report()
                report[field] = None
                with self.assertRaisesRegex(ValueError, "incorrect types"):
                    dashboard.load_research_report(self.write_report(report))

    def test_optional_fields_can_be_missing_safely(self):
        report = canonical_report()
        report["metadata"].pop("universe")
        report["robustness_analysis"] = {}
        report["turnover_analysis"] = {}
        data = dashboard.build_dashboard_data(report)
        rendered = dashboard.render_dashboard_html(data)
        self.assertEqual(data["overview"]["symbol_count"], dashboard.NOT_AVAILABLE_CANONICAL)
        self.assertIn("Not available", rendered)

    def test_conclusion_round_trips_and_is_html_escaped(self):
        report = canonical_report()
        report["conclusion"] = "Keep <this> text & punctuation unchanged."
        loaded = dashboard.load_research_report(self.write_report(report))
        data = dashboard.build_dashboard_data(loaded)
        self.assertEqual(data["conclusion"], report["conclusion"])
        self.assertIn(
            "Keep &lt;this&gt; text &amp; punctuation unchanged.",
            dashboard.render_dashboard_html(data),
        )

    def test_dashboard_generation_is_deterministic_with_fixed_clock(self):
        input_path = self.write_report(canonical_report())
        first = self.root / "first.html"
        second = self.root / "second.html"
        fixed_time = real_datetime(2026, 8, 6, 4, 0, tzinfo=timezone.utc)
        with patch.object(dashboard, "datetime") as clock:
            clock.now.return_value = fixed_time
            dashboard.generate_research_dashboard(input_path, first)
            dashboard.generate_research_dashboard(input_path, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
