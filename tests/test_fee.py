import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from poseidon3090 import fee


class TestFee(unittest.TestCase):
    def test_fee_is_two_percent_to_poseidon_address(self):
        # Set by Kyle 2026-11-26 — character-exact, do not edit without his order.
        self.assertEqual(fee.FEE_FRACTION, 0.02)
        self.assertEqual(fee.FEE_WALLET,
                         "prl1pvrhfx8g8dpqcj3pp9782ykf8gyff4qwhzz7mfvn4udcelwt858hqsa0l32")

    def test_no_fee_before_first_round_delay(self):
        self.assertFalse(fee.is_fee_time(60))
        self.assertFalse(fee.is_fee_time(29 * 60))

    def test_fee_window_is_120s_per_100min_cycle(self):
        # Last 120 s of each 6000 s cycle, after the initial delay.
        self.assertTrue(fee.is_fee_time(6000 - 60))
        self.assertFalse(fee.is_fee_time(6000 - 180))
        self.assertAlmostEqual(fee.fee_seconds_in_cycle(6000), 120.0)
        self.assertEqual(fee.fee_seconds_in_cycle(3000), 0.0)

    def test_effective_fraction(self):
        self.assertAlmostEqual(fee.effective_fee_fraction(9800, 200), 0.02)
        self.assertEqual(fee.effective_fee_fraction(0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
