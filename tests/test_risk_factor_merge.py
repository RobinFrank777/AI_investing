import tempfile
import unittest
from pathlib import Path

import pandas as pd

import risk_factor_merge as subject


def factor_data(statuses=("PASS", "PASS")):
    return pd.DataFrame(
        {
            "Ticker": ["A", "B"],
            "TrendValue": [0.1, 0.2],
            "MomentumValue": [0.2, 0.3],
            "Volatility20D": [0.3, 0.4],
            "FactorStatus": list(statuses),
            "FactorError": ["", ""],
        }
    )


def risk_data(statuses=("PASS", "PASS"), tickers=("A", "B")):
    size = len(tickers)
    return pd.DataFrame(
        {
            "Ticker": list(tickers),
            "AnnualizedVolatility": [0.2] * size,
            "MaxDrawdown": [-0.1] * size,
            "SharpeRatio": [1.5] * size,
            "ObservationCount": [300] * size,
            "Status": list(statuses),
        }
    )


class RiskFactorMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_csv(self, frame, name):
        path = self.root / name
        frame.to_csv(path, index=False)
        return path

    def test_normal_pass_merge(self):
        result = subject.merge_risk_and_factor(
            factor_data(), risk_data()
        )
        self.assertEqual(result["Ticker"].tolist(), ["A", "B"])
        self.assertEqual(result["ResearchStatus"].tolist(), ["PASS", "PASS"])
        self.assertEqual(result["RiskStatus"].tolist(), ["PASS", "PASS"])

    def test_missing_or_partial_risk_produces_partial_research(self):
        factors = factor_data()
        risks = risk_data(statuses=("PARTIAL",), tickers=("A",))
        result = subject.merge_risk_and_factor(factors, risks).set_index("Ticker")
        self.assertEqual(result.at["A", "RiskStatus"], "PARTIAL")
        self.assertEqual(result.at["A", "ResearchStatus"], "PARTIAL")
        self.assertEqual(result.at["B", "RiskStatus"], "FAILED")
        self.assertEqual(result.at["B", "ResearchStatus"], "PARTIAL")
        self.assertTrue(pd.isna(result.at["B", "SharpeRatio"]))

    def test_both_failed_produces_failed_research(self):
        result = subject.merge_risk_and_factor(
            factor_data(statuses=("FAILED", "PASS")),
            risk_data(statuses=("FAILED", "PASS")),
        )
        self.assertEqual(result.at[0, "ResearchStatus"], "FAILED")
        self.assertEqual(result.at[1, "ResearchStatus"], "PASS")

    def test_output_field_integrity_and_factor_order(self):
        factors = factor_data().iloc[::-1].reset_index(drop=True)
        result = subject.merge_risk_and_factor(factors, risk_data())
        self.assertEqual(result["Ticker"].tolist(), ["B", "A"])
        for column in (
            *subject.FACTOR_REQUIRED_COLUMNS,
            *subject.RISK_METRIC_COLUMNS,
            "RiskStatus",
            "ResearchStatus",
        ):
            self.assertIn(column, result.columns)

    def test_missing_required_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "FactorStatus"):
            subject.merge_risk_and_factor(
                factor_data().drop(columns=["FactorStatus"]), risk_data()
            )
        with self.assertRaisesRegex(ValueError, "ObservationCount"):
            subject.merge_risk_and_factor(
                factor_data(), risk_data().drop(columns=["ObservationCount"])
            )

    def test_missing_input_file_has_clear_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "factor data file not found"):
            subject.run_risk_factor_merge(
                self.root / "missing-factor.csv", self.root / "missing-risk.csv"
            )

    def test_empty_data_produces_legal_empty_result(self):
        factors = pd.DataFrame(columns=subject.FACTOR_REQUIRED_COLUMNS)
        risks = pd.DataFrame(columns=subject.RISK_REQUIRED_COLUMNS)
        result = subject.merge_risk_and_factor(factors, risks)
        self.assertTrue(result.empty)
        self.assertIn("ResearchStatus", result.columns)
        self.assertIn("RiskStatus", result.columns)

    def test_invalid_single_status_is_isolated(self):
        factors = factor_data(statuses=("bad", "PASS"))
        result = subject.merge_risk_and_factor(factors, risk_data())
        self.assertEqual(result.at[0, "FactorStatus"], "FAILED")
        self.assertEqual(result.at[0, "ResearchStatus"], "PARTIAL")
        self.assertEqual(result.at[1, "ResearchStatus"], "PASS")

    def test_run_saves_expected_artifact(self):
        factor_path = self.write_csv(factor_data(), "factor.csv")
        risk_path = self.write_csv(risk_data(), "risk.csv")
        output = self.root / "results" / "universe150_research_raw.csv"
        result = subject.run_risk_factor_merge(factor_path, risk_path, output)
        self.assertEqual(result["output_path"], str(output))
        self.assertEqual(result["summary"], {"total": 2, "pass": 2, "partial": 0, "failed": 0})
        self.assertTrue(output.is_file())

    def test_no_forbidden_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        forbidden_references = (
            "factor_ranking",
            "factor_normalization",
            "import portfolio",
            "import watchlist",
            "import broker",
            "import order",
            "generate_signal",
        )
        for reference in forbidden_references:
            with self.subTest(reference=reference):
                self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
