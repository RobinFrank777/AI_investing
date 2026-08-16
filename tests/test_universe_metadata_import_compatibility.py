import ast
import inspect
import unittest
from pathlib import Path

import pandas as pd

import universe_metadata as root_metadata
from src.universe import universe_metadata as canonical_metadata


PUBLIC_FUNCTIONS = (
    "universe_compatibility",
    "tag_current_universe",
    "dataframe_universe_compatibility",
)
PUBLIC_CONSTANTS = (
    "PRIMARY_UNIVERSE_VERSION",
    "UNIVERSE_VERSION_FIELD",
    "MATCH",
    "MISMATCH",
    "MISSING",
)


class UniverseMetadataImportCompatibilityTests(unittest.TestCase):
    def test_root_and_canonical_functions_are_identical(self):
        for name in PUBLIC_FUNCTIONS:
            with self.subTest(name=name):
                root = getattr(root_metadata, name)
                canonical = getattr(canonical_metadata, name)
                self.assertIs(root, canonical)
                self.assertEqual(inspect.signature(root), inspect.signature(canonical))

    def test_root_and_canonical_constants_are_identical(self):
        for name in PUBLIC_CONSTANTS:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(root_metadata, name),
                    getattr(canonical_metadata, name),
                )

    def test_behavior_order_and_exceptions_match(self):
        frame = pd.DataFrame({"Ticker": ["B", "A"], "Value": [1.0, float("nan")]})
        for module in (root_metadata, canonical_metadata):
            with self.subTest(module=module.__name__):
                tagged = module.tag_current_universe(frame)
                self.assertEqual(tagged["Ticker"].tolist(), ["B", "A"])
                self.assertEqual(
                    module.dataframe_universe_compatibility(tagged),
                    module.MATCH,
                )
                self.assertEqual(module.universe_compatibility(None), module.MISSING)
                with self.assertRaisesRegex(TypeError, "pandas DataFrame"):
                    module.tag_current_universe(["B", "A"])

    def test_existing_production_callers_still_reference_root_exports(self):
        import combined_scoring
        import production_candidate_builder
        import rank_stocks_v2
        import report_artifact_consistency

        self.assertIs(combined_scoring.tag_current_universe, root_metadata.tag_current_universe)
        self.assertIs(rank_stocks_v2.tag_current_universe, root_metadata.tag_current_universe)
        self.assertIs(
            production_candidate_builder.dataframe_universe_compatibility,
            root_metadata.dataframe_universe_compatibility,
        )
        self.assertIs(
            report_artifact_consistency.dataframe_universe_compatibility,
            root_metadata.dataframe_universe_compatibility,
        )

    def test_root_wrapper_has_no_implementation_or_duplicate_constants(self):
        tree = ast.parse(Path(root_metadata.__file__).read_text(encoding="utf-8"))
        self.assertFalse(
            any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in tree.body)
        )
        assigned_names = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.assertEqual(assigned_names, {"__all__"})


if __name__ == "__main__":
    unittest.main()
