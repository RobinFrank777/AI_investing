import ast
import inspect
import unittest
from pathlib import Path

import pandas as pd

import research_schema as root_schema
from src.research import research_schema as canonical_schema


PUBLIC_FUNCTIONS = ("normalize_research_schema", "validate_research_schema")
PUBLIC_CONSTANTS = ("STANDARD_FIELDS", "FIELD_ALIASES")


class ResearchSchemaImportCompatibilityTests(unittest.TestCase):
    def test_root_and_canonical_functions_and_signatures_are_identical(self):
        for name in PUBLIC_FUNCTIONS:
            with self.subTest(name=name):
                root = getattr(root_schema, name)
                canonical = getattr(canonical_schema, name)
                self.assertIs(root, canonical)
                self.assertEqual(inspect.signature(root), inspect.signature(canonical))

    def test_root_and_canonical_constants_are_identical(self):
        for name in PUBLIC_CONSTANTS:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(root_schema, name),
                    getattr(canonical_schema, name),
                )

    def test_alias_normalization_field_order_and_dtypes_match(self):
        source = pd.DataFrame(
            {"Symbol": ["B", "A"], "CompositeSignal": ["WATCH", "BUY"], "Value": [2, 1]},
            index=pd.Index([5, 3], name="row"),
        )
        root = root_schema.normalize_research_schema(source)
        canonical = canonical_schema.normalize_research_schema(source)
        pd.testing.assert_frame_equal(root, canonical)
        self.assertEqual(root.index.tolist(), [5, 3])
        self.assertEqual(root.columns.tolist(), ["Symbol", "CompositeSignal", "Value", "Ticker", "Signal"])

    def test_empty_missing_and_exception_behavior_match(self):
        for module in (root_schema, canonical_schema):
            with self.subTest(module=module.__name__):
                empty = module.normalize_research_schema(None)
                self.assertEqual(empty.columns.tolist(), ["Ticker", "Signal"])
                with self.assertRaisesRegex(TypeError, "pandas DataFrame"):
                    module.normalize_research_schema([])
                with self.assertRaisesRegex(ValueError, "Ticker"):
                    module.validate_research_schema(pd.DataFrame({"Signal": ["BUY"]}))

    def test_existing_callers_resolve_to_canonical_function(self):
        import ai_research_summary_builder
        import candidate_report_builder
        import daily_research_snapshot
        import research_candidate_selector
        import research_explanation_engine
        import research_report_composer
        import risk_factor_merge

        callers = (
            ai_research_summary_builder,
            candidate_report_builder,
            daily_research_snapshot,
            research_candidate_selector,
            research_explanation_engine,
            research_report_composer,
            risk_factor_merge,
        )
        for caller in callers:
            with self.subTest(caller=caller.__name__):
                self.assertIs(
                    caller.normalize_research_schema,
                    canonical_schema.normalize_research_schema,
                )

    def test_root_wrapper_has_no_implementation_or_duplicate_schema(self):
        tree = ast.parse(Path(root_schema.__file__).read_text(encoding="utf-8"))
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
