import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_research_report as report
from factor_validation import (
    VALIDATION_COLUMNS, build_group_return_table, build_rank_ic_table,
    build_turnover_table,
)


def observations():
    rows = []
    for date in ("2026-01-30", "2026-02-27"):
        for index, ticker in enumerate(("A", "B", "C", "D", "E"), start=1):
            row = {column: None for column in VALIDATION_COLUMNS}
            row.update({
                "RebalanceDate": date, "Ticker": ticker,
                "CompositeFactorScore": index / 5,
                "TrendPercentile": index / 5,
                "MomentumPercentile": (6 - index) / 5,
                "LowVolatilityPercentile": [0.4, 0.8, 0.2, 1.0, 0.6][index - 1],
                **{f"ForwardReturn{horizon}D": index / 100 for horizon in (5, 10, 20, 60)},
            })
            rows.append(row)
    return pd.DataFrame(rows, columns=VALIDATION_COLUMNS)


class FactorResearchReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def paths(self):
        validation = observations()
        core_tables = {
            "validation": validation,
            "rank_ic": build_rank_ic_table(validation),
            "group_returns": build_group_return_table(validation),
            "turnover": build_turnover_table(validation),
        }
        core = {}
        for name, table in core_tables.items():
            core[name] = self.root / f"scale50_{name}.csv"
            table.to_csv(core[name], index=False)
        robust_tables = {
            "robust_stats": pd.DataFrame([{"Horizon": "5D", "Series": "Top-Bottom", "ObservationCount": 2, "PositiveRatio": .5}]),
            "regimes": pd.DataFrame([{"Regime": "All", "Horizon": "5D", "MeanRankIC": .1}]),
            "coverage": pd.DataFrame([{"RebalanceDate": "2026-01-30", "ScoreCoverageRatio": 1.0}]),
        }
        robust = {}
        for name, table in robust_tables.items():
            robust[name] = self.root / f"scale50_{name}.csv"
            table.to_csv(robust[name], index=False)
        return core, robust

    def test_module_imports(self):
        self.assertTrue(hasattr(report, "FactorResearchReport"))

    def test_input_files_exist_check(self):
        core, robust = self.paths(); robust["coverage"] = self.root / "missing.csv"
        with self.assertRaises(FileNotFoundError):
            report.FactorResearchReport(core, robust).build_report()

    def test_json_output_generated(self):
        core, robust = self.paths(); output = self.root / "report.json"
        generator = report.FactorResearchReport(core, robust)
        generator.build_report(); generator.export_json(output)
        self.assertIn("factor_model", json.loads(output.read_text()))

    def test_html_output_generated(self):
        core, robust = self.paths(); output = self.root / "report.html"
        generator = report.FactorResearchReport(core, robust)
        generator.build_report(); generator.export_html(output)
        self.assertIn("Research Limitations", output.read_text())

    def test_required_fields_exist(self):
        core, robust = self.paths()
        result = report.FactorResearchReport(core, robust).build_report()
        self.assertTrue({"factor_model", "ic_analysis", "limitations"}.issubset(result))

    def test_default_factor_weights(self):
        core, robust = self.paths()
        components = report.FactorResearchReport(core, robust).build_report()["factor_model"]["components"]
        self.assertEqual([item["weight"] for item in components], [.35, .35, .30])

    def test_generate_writes_both_formats(self):
        core, robust = self.paths()
        html_path, json_path = self.root / "x.html", self.root / "x.json"
        result = report.generate_factor_research_report(
            core, robust, html_path=html_path, json_path=json_path
        )
        self.assertTrue(Path(result["html_path"]).is_file())
        self.assertTrue(Path(result["json_path"]).is_file())

    def test_cli_success_output(self):
        with patch.object(report, "generate_factor_research_report", return_value={"html_path": "results/scale50_factor_report.html", "json_path": "results/scale50_factor_report.json", "report": {"metadata": {"universe": "Scale50"}}}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(report.main(), 0)
        self.assertIn("scale50_factor_report.json", output.getvalue())


if __name__ == "__main__":
    unittest.main()
