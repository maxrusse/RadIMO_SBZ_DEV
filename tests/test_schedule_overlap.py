import unittest
from datetime import time, date

import pandas as pd

from data_manager.schedule_crud import (
    resolve_overlapping_shifts,
    _recalculate_worker_shift_durations,
)


class TestScheduleOverlap(unittest.TestCase):
    def test_resolve_overlapping_shifts_crops_earlier(self) -> None:
        target_date = date(2026, 1, 23)
        shifts = [
            {"PPL": "Alice", "start_time": time(8, 0), "end_time": time(12, 0)},
            {"PPL": "Alice", "start_time": time(10, 0), "end_time": time(14, 0)},
        ]

        resolved = resolve_overlapping_shifts(shifts, target_date)
        self.assertEqual(len(resolved), 2)
        first, second = resolved

        self.assertEqual(first["start_time"], time(8, 0))
        self.assertEqual(first["end_time"], time(10, 0))
        self.assertAlmostEqual(first["shift_duration"], 2.0)

        self.assertEqual(second["start_time"], time(10, 0))
        self.assertEqual(second["end_time"], time(14, 0))
        self.assertAlmostEqual(second["shift_duration"], 4.0)

    def test_recalculate_worker_shift_durations_applies_gaps(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "PPL": "Bob",
                    "row_type": "shift",
                    "start_time": time(8, 0),
                    "end_time": time(12, 0),
                    "counts_for_hours": True,
                    "shift_duration": 4.0,
                },
                {
                    "PPL": "Bob",
                    "row_type": "shift",
                    "start_time": time(9, 30),
                    "end_time": time(10, 30),
                    "counts_for_hours": True,
                    "shift_duration": 1.0,
                },
                {
                    "PPL": "Bob",
                    "row_type": "gap",
                    "start_time": time(9, 0),
                    "end_time": time(10, 0),
                    "counts_for_hours": False,
                    "shift_duration": 0.0,
                },
                {
                    "PPL": "Bob",
                    "row_type": "gap",
                    "start_time": time(11, 0),
                    "end_time": time(13, 0),
                    "counts_for_hours": False,
                    "shift_duration": 0.0,
                },
            ]
        )

        _recalculate_worker_shift_durations(df, "Bob")

        first_shift = df.iloc[0]
        self.assertAlmostEqual(first_shift["shift_duration"], 2.0)

        second_shift = df.iloc[1]
        self.assertAlmostEqual(second_shift["shift_duration"], 0.5)

    def test_recalculate_worker_shift_durations_zeroes_full_gaps(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "PPL": "Cara",
                    "row_type": "shift",
                    "start_time": time(13, 0),
                    "end_time": time(14, 0),
                    "counts_for_hours": True,
                    "shift_duration": 1.0,
                },
                {
                    "PPL": "Cara",
                    "row_type": "gap",
                    "start_time": time(13, 0),
                    "end_time": time(14, 0),
                    "counts_for_hours": False,
                    "shift_duration": 0.0,
                },
            ]
        )

        _recalculate_worker_shift_durations(df, "Cara")

        shift_row = df.iloc[0]
        self.assertEqual(shift_row["shift_duration"], 0.0)
        self.assertFalse(shift_row["counts_for_hours"])


if __name__ == "__main__":
    unittest.main()
