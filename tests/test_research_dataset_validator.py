import tempfile
import unittest
from pathlib import Path

import pandas as pd

import research_dataset_validator as subject


def complete_data():
    return pd.DataFrame(
        {
            "Ticker": ["A", "B", "C"],
            "TrendValue": [0.1, 0.2, 0.3],
            "MomentumValue": [0.2, 0.3, 0.4],
            "Volatility20D": [0.3, 0.4, 0.5],
            "TrendScore": [0.8, 0.6, 0.4],
            "MomentumScore": [0.9, 0.7, 0.3],
            "LowVolScore": [0.7, 0.5, 0.2],
            "CompositeScore": [0.81, 0.61, 0.31],
            "Rank": [1, 2, 3],
            "TrendSignal": ["STRONG", "NORMAL", "WEAK"],
            "MomentumSignal": ["POSITIVE", "NEUTRAL", "NEGATIVE"],
            "VolatilitySignal": ["LOW", "NORMAL", "HIGH"],
            "CompositeSignal": ["B", "C", "D"],
            "Signal": ["B", "C", "D"],
            "FactorStatus": ["PASS", "PASS", "FAILED"],
            "FactorError": ["", "", "invalid prices"],
            "AnnualizedVolatility": [0.2, 0.3, 0.4],
            "MaxDrawdown": [-0.1, -0.2, -0.3],
            "SharpeRatio": [1.5, 1.0, 0.5],
            "ObservationCount": [300, 300, 300],
            "RiskStatus": ["PASS", "PARTIAL", "FAILED"],
            "ResearchStatus": ["PASS", "PARTIAL", "FAILED"],
        }
    )


def value_for(validation, item):
    return validation.set_index("CheckItem").at[item, "Value"]


class ResearchDatasetValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_with(self, frame):
        input_path = self.root / "universe150_research_raw.csv"
        output_path = self.root / "universe150_research_validation.csv"
        frame.to_csv(input_path, index=False)
        result = subject.validate_research_dataset(input_path, output_path)
        self.assertTrue(output_path.is_file())
        self.assertEqual(tuple(result.columns), subject.OUTPUT_COLUMNS)
        return result

    def test_complete_dataset_passes(self):
        result = self.run_with(complete_data())
        self.assertEqual(value_for(result, "OverallStatus"), "PASS")
        self.assertEqual(value_for(result, "TotalRows"), 3)
        self.assertEqual(value_for(result, "UniqueTickers"), 3)
        self.assertEqual(value_for(result, "ResearchPASSCount"), 1)
        self.assertEqual(value_for(result, "ResearchPARTIALCount"), 1)
        self.assertEqual(value_for(result, "ResearchFAILEDCount"), 1)

    def test_missing_required_column_fails(self):
        result = self.run_with(complete_data().drop(columns=["SharpeRatio"]))
        self.assertEqual(value_for(result, "OverallStatus"), "FAILED")
        self.assertIn("SharpeRatio", value_for(result, "MissingRequiredColumns"))

    def test_duplicate_ticker_is_counted(self):
        data = complete_data()
        data.loc[2, "Ticker"] = "A"
        result = self.run_with(data)
        self.assertEqual(value_for(result, "DuplicateTickers"), 1)
        self.assertEqual(value_for(result, "OverallStatus"), "PARTIAL")

    def test_empty_ticker_is_counted(self):
        data = complete_data()
        data.loc[1, "Ticker"] = "  "
        data.loc[2, "Ticker"] = None
        result = self.run_with(data)
        self.assertEqual(value_for(result, "MissingTickerCount"), 2)
        self.assertEqual(value_for(result, "OverallStatus"), "PARTIAL")

    def test_invalid_research_status_fails_status_check(self):
        data = complete_data()
        data.loc[0, "ResearchStatus"] = "UNKNOWN"
        result = self.run_with(data)
        indexed = result.set_index("CheckItem")
        self.assertEqual(indexed.at["InvalidResearchStatusCount", "Value"], 1)
        self.assertEqual(indexed.at["InvalidResearchStatusCount", "Status"], "PARTIAL")
        self.assertEqual(indexed.at["OverallStatus", "Value"], "PARTIAL")

    def test_empty_file_returns_legal_result(self):
        input_path = self.root / "empty.csv"
        input_path.write_text("", encoding="utf-8")
        output_path = self.root / "validation.csv"
        result = subject.validate_research_dataset(input_path, output_path)
        self.assertEqual(value_for(result, "OverallStatus"), "PARTIAL")
        self.assertEqual(value_for(result, "TotalRows"), 0)
        self.assertTrue(output_path.is_file())

    def test_missing_file_returns_failed_result(self):
        output_path = self.root / "validation.csv"
        result = subject.validate_research_dataset(
            self.root / "missing.csv", output_path
        )
        self.assertEqual(value_for(result, "OverallStatus"), "FAILED")
        self.assertTrue(output_path.is_file())

    def test_missing_metric_value_is_partial(self):
        data = complete_data()
        data.loc[0, "SharpeRatio"] = None
        result = self.run_with(data)
        self.assertEqual(value_for(result, "MissingMetricValueCount"), 1)
        self.assertEqual(value_for(result, "OverallStatus"), "PARTIAL")

    def test_no_forbidden_dependencies(self):
        source = Path(subject.__file__).read_text(encoding="utf-8")
        for forbidden in ("portfolio", "watchlist", "broker", "order", "trading"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
