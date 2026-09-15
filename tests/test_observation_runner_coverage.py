
import unittest
import observation_runner as subject


class ObservationCoverageStatusTests(unittest.TestCase):
    def classify(self, **overrides):
        values = {
            "configured": 150,
            "ready": 150,
            "excluded": 0,
            "provider_rejected": 0,
            "stale_market_data": 0,
            "insufficient_history": 0,
            "excluded_symbols": "",
        }
        values.update(overrides)
        return subject.classify_observation_coverage_status(**values)

    def test_full(self):
        self.assertEqual(self.classify(), "FULL")

    def test_insufficient_history_only_is_normal_baseline_for_any_ticker(self):
        self.assertEqual(
            self.classify(
                ready=149,
                excluded=1,
                insufficient_history=1,
                excluded_symbols="NEWIPO (INSUFFICIENT_HISTORY)",
            ),
            "NORMAL_BASELINE",
        )

    def test_provider_rejection_without_stale(self):
        self.assertEqual(
            self.classify(
                ready=144,
                excluded=6,
                provider_rejected=4,
                insufficient_history=2,
                excluded_symbols=(
                    "SKHY (INSUFFICIENT_HISTORY), SPCX (INSUFFICIENT_HISTORY), "
                    "TSM (PROVIDER_REJECTED), LMND (PROVIDER_REJECTED), "
                    "MCD (PROVIDER_REJECTED), DIS (PROVIDER_REJECTED)"
                ),
            ),
            "PARTIAL_PROVIDER_REJECTION",
        )

    def test_stale_has_priority_over_provider_rejection(self):
        self.assertEqual(
            self.classify(
                ready=146,
                excluded=4,
                provider_rejected=1,
                stale_market_data=1,
                insufficient_history=2,
                excluded_symbols=(
                    "AAA (PROVIDER_REJECTED), BBB (STALE_MARKET_DATA), "
                    "SKHY (INSUFFICIENT_HISTORY), SPCX (INSUFFICIENT_HISTORY)"
                ),
            ),
            "DATA_READINESS_EXCEPTION",
        )

    def test_unknown_reason_fails_closed(self):
        with self.assertRaises(RuntimeError):
            self.classify(
                ready=149,
                excluded=1,
                excluded_symbols="AAA (NEW_REASON)",
            )

    def test_count_mismatch_fails_closed(self):
        with self.assertRaises(RuntimeError):
            self.classify(
                ready=148,
                excluded=2,
                provider_rejected=1,
                insufficient_history=1,
                excluded_symbols=(
                    "AAA (PROVIDER_REJECTED), BBB (PROVIDER_REJECTED)"
                ),
            )

    def test_final_authority_semantics(self):
        self.assertEqual(
            self.classify(
                ready=148,
                excluded=2,
                provider_rejected=0,
                stale_market_data=0,
                insufficient_history=2,
                excluded_symbols=(
                    "SKHY (INSUFFICIENT_HISTORY), SPCX (INSUFFICIENT_HISTORY)"
                ),
            ),
            "NORMAL_BASELINE",
        )


if __name__ == "__main__":
    unittest.main()
