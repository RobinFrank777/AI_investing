import ast
import unittest
from pathlib import Path

import pandas as pd

import price_factors as root_price_factors
from src.research.technical import price_factors as canonical_price_factors


PUBLIC_FUNCTIONS = (
    "calculate_trend_value",
    "calculate_momentum_value",
    "calculate_volatility_20d",
    "calculate_price_factors",
)
PUBLIC_CONSTANTS = (
    "TREND_OBSERVATIONS",
    "MOMENTUM_OBSERVATIONS",
    "VOLATILITY_OBSERVATIONS",
)


class PriceFactorsImportCompatibilityTests(unittest.TestCase):
    def test_root_and_canonical_functions_are_identical_references(self):
        for name in PUBLIC_FUNCTIONS:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(root_price_factors, name),
                    getattr(canonical_price_factors, name),
                )

    def test_root_and_canonical_constants_match(self):
        for name in PUBLIC_CONSTANTS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(root_price_factors, name),
                    getattr(canonical_price_factors, name),
                )

    def test_root_all_exposes_the_complete_supported_api(self):
        self.assertEqual(
            set(root_price_factors.__all__),
            set(PUBLIC_FUNCTIONS + PUBLIC_CONSTANTS),
        )

    def test_results_and_invalid_value_behavior_match(self):
        values = list(range(1, 61))
        values[10] = float("nan")
        frame = pd.DataFrame({"Close": values + [61]})
        self.assertEqual(
            root_price_factors.calculate_price_factors(frame),
            canonical_price_factors.calculate_price_factors(frame),
        )

    def test_exceptions_match(self):
        for module in (root_price_factors, canonical_price_factors):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Close"):
                    module.calculate_price_factors(pd.DataFrame({"Open": [1]}))

    def test_root_wrapper_contains_no_calculation_implementation(self):
        source = Path(root_price_factors.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertFalse(any(isinstance(node, ast.FunctionDef) for node in tree.body))
        assigned_names = {
            target.id
            for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)
        }
        self.assertEqual(assigned_names, {"__all__"})


if __name__ == "__main__":
    unittest.main()
