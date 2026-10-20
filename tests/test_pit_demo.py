"""Checks that synthetic PIT data cannot leak into earlier dates."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from pit_demo import DataNotYetAvailable, Observation, PITView, synthetic_data


class PITDemoTests(unittest.TestCase):
    def setUp(self):
        self.view = PITView(synthetic_data())

    def test_unavailable_first_bar_is_rejected(self):
        with self.assertRaises(DataNotYetAvailable):
            self.view.latest(date(2026, 1, 5), "SYN")

    def test_only_available_bar_is_visible(self):
        self.assertEqual(self.view.latest(date(2026, 1, 6), "SYN").close, 100.0)
        self.assertEqual(self.view.latest(date(2026, 1, 7), "SYN").close, 102.0)

    def test_unknown_symbol_is_rejected(self):
        with self.assertRaises(DataNotYetAvailable):
            self.view.latest(date(2026, 1, 8), "UNKNOWN")

    def test_bad_available_date_rejected(self):
        with self.assertRaises(ValueError):
            Observation("SYN", date(2026, 1, 5), date(2026, 1, 4), 100.0)

    def test_nonpositive_price_rejected(self):
        with self.assertRaises(ValueError):
            Observation("SYN", date(2026, 1, 5), date(2026, 1, 6), -1.0)


if __name__ == "__main__":
    unittest.main()
