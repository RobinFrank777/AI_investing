import tempfile
import unittest
from pathlib import Path

import pandas as pd

import factor_report as report
from factor_validation import (
    VALIDATION_COLUMNS, build_group_return_table, build_rank_ic_table,
    build_turnover_table,
)


def validation_table():
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


class FactorReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def artifacts(self, prefix=""):
        validation = validation_table()
        tables = {
            "validation": validation,
            "rank_ic": build_rank_ic_table(validation),
            "group_returns": build_group_return_table(validation),
            "turnover": build_turnover_table(validation),
        }
        paths = {}
        for name, table in tables.items():
            path = self.root / f"{prefix}{name}.csv"
            table.to_csv(path, index=False)
            paths[name] = path
        return paths

    def test_report_generation(self):
        result = report.generate_factor_report(self.artifacts(), save=False)
        self.assertEqual(result["summary"]["universe"], "Production")
        self.assertEqual(len(result["summary"]["factor_ranking"]), 3)

    def test_output_file_creation(self):
        output = self.root / "report.html"
        result = report.generate_factor_report(self.artifacts(), output_path=output)
        self.assertEqual(result["report_path"], str(output))
        self.assertIn("Factor Research Report", output.read_text(encoding="utf-8"))

    def test_scale50_default_output_identity(self):
        result = report.generate_factor_report(self.artifacts("scale50_"), save=False)
        self.assertEqual(result["summary"]["universe"], "Scale50")

    def test_summary_structure(self):
        summary = report.generate_factor_report(self.artifacts(), save=False)["summary"]
        self.assertEqual(set(summary), {
            "universe", "period", "rebalance", "horizons", "factor_ranking",
            "composite_rank_ic", "portfolio_groups", "composite_turnover",
            "score_weights", "conclusion",
        })

    def test_missing_columns(self):
        paths = self.artifacts()
        pd.DataFrame({"Ticker": ["A"]}).to_csv(paths["validation"], index=False)
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            report.generate_factor_report(paths, save=False)

    def test_empty_dataframe(self):
        paths = self.artifacts()
        pd.DataFrame(columns=VALIDATION_COLUMNS).to_csv(paths["validation"], index=False)
        with self.assertRaisesRegex(ValueError, "empty"):
            report.generate_factor_report(paths, save=False)

    def test_invalid_paths(self):
        paths = self.artifacts(); paths["rank_ic"] = self.root / "missing.csv"
        with self.assertRaises(FileNotFoundError):
            report.generate_factor_report(paths, save=False)

    def test_factor_ranking_calculation(self):
        ranking = report.generate_factor_report(self.artifacts(), save=False)["summary"]["factor_ranking"]
        self.assertEqual(ranking[0]["factor"], "Trend")
        self.assertEqual([row["rank"] for row in ranking], [1, 2, 3])

    def test_score_calculation(self):
        weights = {"ic": 1.0, "return": 0.0, "stability": 0.0}
        ranking = report.generate_factor_report(
            self.artifacts(), save=False, score_weights=weights
        )["summary"]["factor_ranking"]
        self.assertEqual(ranking[0]["score"], ranking[0]["ic_score"])

    def test_invalid_score_weights(self):
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            report.generate_factor_report(
                self.artifacts(), save=False,
                score_weights={"ic": .5, "return": .5, "stability": .5},
            )


if __name__ == "__main__":
    unittest.main()
