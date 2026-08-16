import ast
import inspect
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import market_session as root_session
from src.data import market_session as canonical_session


PUBLIC_FUNCTIONS = (
    "current_us_session_is_complete",
    "completed_daily_bars",
    "latest_completed_session_date",
)
PUBLIC_CONSTANTS = ("NEW_YORK", "DAILY_BAR_COMPLETION_TIME")
EASTERN = ZoneInfo("America/New_York")


class MarketSessionImportCompatibilityTests(unittest.TestCase):
    def test_root_and_canonical_functions_and_signatures_are_identical(self):
        for name in PUBLIC_FUNCTIONS:
            with self.subTest(name=name):
                root = getattr(root_session, name)
                canonical = getattr(canonical_session, name)
                self.assertIs(root, canonical)
                self.assertEqual(inspect.signature(root), inspect.signature(canonical))

    def test_root_and_canonical_constants_are_identical(self):
        for name in PUBLIC_CONSTANTS:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(root_session, name),
                    getattr(canonical_session, name),
                )

    def test_cutoff_weekend_and_timezone_behavior_match(self):
        moments = (
            datetime(2026, 6, 18, 16, 14, 59, tzinfo=EASTERN),
            datetime(2026, 6, 18, 16, 15, tzinfo=EASTERN),
            datetime(2026, 6, 20, 10, 0, tzinfo=EASTERN),
            datetime(2026, 6, 18, 20, 14, 59, tzinfo=timezone.utc),
        )
        for moment in moments:
            with self.subTest(moment=moment):
                self.assertEqual(
                    root_session.current_us_session_is_complete(moment),
                    canonical_session.current_us_session_is_complete(moment),
                )
                self.assertEqual(
                    root_session.latest_completed_session_date(moment),
                    canonical_session.latest_completed_session_date(moment),
                )

    def test_dst_and_daily_bar_filtering_match(self):
        frame = pd.DataFrame(
            {"Close": [10.0, 11.0]},
            index=pd.DatetimeIndex(["2026-03-06", "2026-03-09"]),
        )
        before_cutoff = datetime(2026, 3, 9, 15, 0, tzinfo=EASTERN)
        after_cutoff = datetime(2026, 3, 9, 16, 15, tzinfo=EASTERN)
        for moment in (before_cutoff, after_cutoff):
            with self.subTest(moment=moment):
                pd.testing.assert_frame_equal(
                    root_session.completed_daily_bars(frame, moment),
                    canonical_session.completed_daily_bars(frame, moment),
                )

    def test_naive_datetime_exception_matches(self):
        for module in (root_session, canonical_session):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "timezone-aware"):
                    module.latest_completed_session_date(datetime(2026, 6, 18, 12, 0))

    def test_existing_callers_still_resolve_to_canonical_objects(self):
        import current_run_status
        import rank_stocks_v2
        import run_all
        import update_data

        self.assertIs(
            current_run_status.latest_completed_session_date,
            canonical_session.latest_completed_session_date,
        )
        self.assertIs(
            rank_stocks_v2.latest_completed_session_date,
            canonical_session.latest_completed_session_date,
        )
        self.assertIs(
            run_all.latest_completed_session_date,
            canonical_session.latest_completed_session_date,
        )
        self.assertIs(update_data.completed_daily_bars, canonical_session.completed_daily_bars)

    def test_root_wrapper_has_no_implementation_or_independent_constants(self):
        tree = ast.parse(Path(root_session.__file__).read_text(encoding="utf-8"))
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
