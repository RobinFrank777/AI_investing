import unittest

import signal_contract as subject


class SignalContractTests(unittest.TestCase):
    def test_trend_strong_maps_to_bullish(self):
        self.assertEqual(subject.normalize_trend_signal("STRONG"), "BULLISH")

    def test_trend_normal_maps_to_neutral(self):
        self.assertEqual(subject.normalize_trend_signal("NORMAL"), "NEUTRAL")

    def test_trend_weak_maps_to_bearish(self):
        self.assertEqual(subject.normalize_trend_signal("WEAK"), "BEARISH")

    def test_trend_unknown_remains_unknown(self):
        self.assertEqual(subject.normalize_trend_signal("UNKNOWN"), "UNKNOWN")

    def test_momentum_positive_maps_to_strong(self):
        self.assertEqual(subject.normalize_momentum_signal("POSITIVE"), "STRONG")

    def test_momentum_neutral_maps_to_normal(self):
        self.assertEqual(subject.normalize_momentum_signal("NEUTRAL"), "NORMAL")

    def test_momentum_negative_maps_to_weak(self):
        self.assertEqual(subject.normalize_momentum_signal("NEGATIVE"), "WEAK")

    def test_momentum_unknown_remains_unknown(self):
        self.assertEqual(subject.normalize_momentum_signal("UNKNOWN"), "UNKNOWN")

    def test_volatility_low_is_preserved(self):
        self.assertEqual(subject.normalize_volatility_signal("LOW"), "LOW")

    def test_volatility_normal_is_preserved(self):
        self.assertEqual(subject.normalize_volatility_signal("NORMAL"), "NORMAL")

    def test_volatility_high_is_preserved(self):
        self.assertEqual(subject.normalize_volatility_signal("HIGH"), "HIGH")

    def test_volatility_unknown_is_preserved(self):
        self.assertEqual(subject.normalize_volatility_signal("UNKNOWN"), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
