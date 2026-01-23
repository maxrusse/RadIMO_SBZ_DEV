import unittest

from lib.utils import merge_intervals, subtract_intervals


class TestIntervalUtils(unittest.TestCase):
    def test_merge_intervals_sorts_and_merges(self) -> None:
        intervals = [(5, 7), (1, 3), (2, 6), (10, 12)]
        self.assertEqual(merge_intervals(intervals), [(1, 7), (10, 12)])

    def test_merge_intervals_handles_touching(self) -> None:
        intervals = [(1, 3), (3, 5)]
        self.assertEqual(merge_intervals(intervals), [(1, 5)])

    def test_subtract_intervals_multiple_gaps(self) -> None:
        base = (0, 10)
        gaps = [(2, 4), (6, 7)]
        self.assertEqual(subtract_intervals(base, gaps), [(0, 2), (4, 6), (7, 10)])

    def test_subtract_intervals_outside_bounds(self) -> None:
        base = (0, 10)
        gaps = [(-2, 1), (9, 12)]
        self.assertEqual(subtract_intervals(base, gaps), [(1, 9)])


if __name__ == "__main__":
    unittest.main()
