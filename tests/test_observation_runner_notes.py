
import unittest

import observation_runner as subject


class ObservationRunnerNotesTests(unittest.TestCase):
    def test_provider_rejection_and_insufficient_history_are_explained(self):
        notes = subject.build_daily_run_notes(
            configured=150,
            ready=144,
            excluded=6,
            provider_rejected=4,
            stale_market_data=0,
            insufficient_history=2,
            excluded_symbols=(
                "SKHY (INSUFFICIENT_HISTORY), "
                "SPCX (INSUFFICIENT_HISTORY), "
                "TSM (PROVIDER_REJECTED), "
                "LMD (PROVIDER_REJECTED), "
                "MCD (PROVIDER_REJECTED), "
                "DIS (PROVIDER_REJECTED)"
            ),
        )
        self.assertIn("Provider rejection: TSM, LMD, MCD, DIS (4)", notes)
        self.assertIn("Stale market data: none", notes)
        self.assertIn("Insufficient history: SKHY, SPCX (2)", notes)
        self.assertIn("Readiness 144/150; excluded 6", notes)

    def test_insufficient_history_only_is_explicit(self):
        notes = subject.build_daily_run_notes(
            configured=150,
            ready=148,
            excluded=2,
            provider_rejected=0,
            stale_market_data=0,
            insufficient_history=2,
            excluded_symbols=(
                "SKHY (INSUFFICIENT_HISTORY), "
                "SPCX (INSUFFICIENT_HISTORY)"
            ),
        )
        self.assertIn("Provider rejection: none", notes)
        self.assertIn("Stale market data: none", notes)
        self.assertIn("Insufficient history: SKHY, SPCX (2)", notes)
        self.assertIn("Readiness 148/150; excluded 2", notes)

    def test_count_mismatch_fails_closed(self):
        with self.assertRaises(RuntimeError):
            subject.build_daily_run_notes(
                configured=150,
                ready=144,
                excluded=6,
                provider_rejected=3,
                stale_market_data=0,
                insufficient_history=2,
                excluded_symbols=(
                    "SKHY (INSUFFICIENT_HISTORY), "
                    "SPCX (INSUFFICIENT_HISTORY), "
                    "TSM (PROVIDER_REJECTED), "
                    "LMD (PROVIDER_REJECTED), "
                    "MCD (PROVIDER_REJECTED), "
                    "DIS (PROVIDER_REJECTED)"
                ),
            )

    def test_unexpected_excluded_symbol_format_fails_closed(self):
        with self.assertRaises(RuntimeError):
            subject.parse_excluded_symbols("TSM: PROVIDER_REJECTED")


if __name__ == "__main__":
    unittest.main()
