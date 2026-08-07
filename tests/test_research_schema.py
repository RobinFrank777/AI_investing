import unittest

import pandas as pd

import research_schema as subject


class ResearchSchemaTests(unittest.TestCase):
    def test_existing_ticker_is_preserved(self):
        data = pd.DataFrame({"Ticker": ["A"], "Signal": ["STRONG"]})
        result = subject.normalize_research_schema(data)
        self.assertEqual(result["Ticker"].tolist(), ["A"])

    def test_symbol_is_mapped_to_ticker(self):
        data = pd.DataFrame({"Symbol": ["A"], "Signal": ["STRONG"]})
        result = subject.normalize_research_schema(data)
        self.assertEqual(result["Ticker"].tolist(), ["A"])
        self.assertIn("Symbol", result.columns)

    def test_ticker_has_priority_and_symbol_fills_blanks(self):
        data = pd.DataFrame(
            {
                "Ticker": ["A", None, ""],
                "Symbol": ["X", "B", "C"],
                "Signal": ["S1", "S2", "S3"],
            }
        )
        result = subject.normalize_research_schema(data)
        self.assertEqual(result["Ticker"].tolist(), ["A", "B", "C"])
        self.assertEqual(result["Symbol"].tolist(), ["X", "B", "C"])

    def test_missing_ticker_sources_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Ticker"):
            subject.normalize_research_schema(pd.DataFrame({"Signal": ["S"]}))

    def test_existing_signal_is_preserved(self):
        data = pd.DataFrame({"Ticker": ["A"], "Signal": ["STRONG"]})
        result = subject.normalize_research_schema(data)
        self.assertEqual(result["Signal"].tolist(), ["STRONG"])

    def test_composite_signal_is_mapped_to_signal(self):
        data = pd.DataFrame({"Ticker": ["A"], "CompositeSignal": ["A"]})
        result = subject.normalize_research_schema(data)
        self.assertEqual(result["Signal"].tolist(), ["A"])
        self.assertIn("CompositeSignal", result.columns)

    def test_signal_has_priority_and_composite_fills_blanks(self):
        data = pd.DataFrame(
            {
                "Ticker": ["A", "B", "C"],
                "Signal": ["STRONG", None, ""],
                "CompositeSignal": ["X", "NORMAL", "WEAK"],
            }
        )
        result = subject.normalize_research_schema(data)
        self.assertEqual(result["Signal"].tolist(), ["STRONG", "NORMAL", "WEAK"])
        self.assertEqual(result["CompositeSignal"].tolist(), ["X", "NORMAL", "WEAK"])

    def test_missing_signal_sources_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Signal"):
            subject.normalize_research_schema(pd.DataFrame({"Ticker": ["A"]}))

    def test_original_fields_and_row_sequence_are_preserved(self):
        data = pd.DataFrame(
            {
                "Symbol": ["B", "A"],
                "CompositeSignal": ["NORMAL", "STRONG"],
                "Rank": [2, 1],
            },
            index=[8, 3],
        )
        result = subject.normalize_research_schema(data)
        self.assertEqual(result.index.tolist(), [8, 3])
        self.assertEqual(result["Symbol"].tolist(), ["B", "A"])
        self.assertEqual(result["Rank"].tolist(), [2, 1])

    def test_empty_dataframe_returns_legal_standard_schema(self):
        result = subject.normalize_research_schema(pd.DataFrame())
        self.assertTrue(result.empty)
        self.assertEqual(tuple(result.columns), subject.STANDARD_FIELDS)
        self.assertTrue(subject.validate_research_schema(result))

    def test_empty_dataframe_preserves_existing_columns(self):
        data = pd.DataFrame(columns=["Symbol", "CompositeSignal", "Extra"])
        result = subject.normalize_research_schema(data)
        self.assertEqual(
            tuple(result.columns),
            ("Symbol", "CompositeSignal", "Extra", "Ticker", "Signal"),
        )

    def test_none_returns_legal_standard_schema(self):
        result = subject.normalize_research_schema(None)
        self.assertTrue(result.empty)
        self.assertEqual(tuple(result.columns), subject.STANDARD_FIELDS)

    def test_validation_rejects_missing_standard_fields(self):
        with self.assertRaisesRegex(ValueError, "Signal"):
            subject.validate_research_schema(pd.DataFrame(columns=["Ticker"]))
        with self.assertRaisesRegex(ValueError, "required"):
            subject.validate_research_schema(None)

    def test_input_dataframe_is_not_modified(self):
        data = pd.DataFrame({"Symbol": ["A"], "CompositeSignal": ["STRONG"]})
        original = data.copy(deep=True)
        subject.normalize_research_schema(data)
        pd.testing.assert_frame_equal(data, original)


if __name__ == "__main__":
    unittest.main()
