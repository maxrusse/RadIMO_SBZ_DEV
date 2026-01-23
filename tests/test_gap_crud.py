import unittest
from datetime import time
from unittest.mock import patch

import pandas as pd

from config import SKILL_COLUMNS, allowed_modalities
from data_manager import schedule_crud


class TestGapCrud(unittest.TestCase):
    def setUp(self) -> None:
        self.modality = allowed_modalities[0]
        base_row = {
            "PPL": "Dana",
            "start_time": time(8, 0),
            "end_time": time(12, 0),
            "Modifier": 1.0,
            "row_type": "shift",
            "counts_for_hours": True,
            "shift_duration": 4.0,
            "tasks": "Shift",
        }
        for skill in SKILL_COLUMNS:
            base_row[skill] = 0
        schedule_crud.modality_data[self.modality]["working_hours_df"] = pd.DataFrame([base_row])

    def test_add_update_remove_gap_row(self) -> None:
        with patch.object(schedule_crud, "backup_dataframe") as backup_mock:
            success, _, error = schedule_crud._add_gap_to_schedule(
                self.modality,
                row_index=0,
                gap_type="Break",
                gap_start="09:00",
                gap_end="10:00",
                use_staged=False,
            )
            self.assertTrue(success, msg=error)

            df = schedule_crud.modality_data[self.modality]["working_hours_df"]
            gap_rows = df[df["row_type"] == "gap"]
            self.assertEqual(len(gap_rows), 1)
            gap_row = gap_rows.iloc[0]
            self.assertEqual(gap_row["tasks"], "Break")
            self.assertFalse(gap_row["counts_for_hours"])
            for skill in SKILL_COLUMNS:
                self.assertEqual(gap_row[skill], -1)

            success, _, error = schedule_crud._update_gap_in_schedule(
                self.modality,
                row_index=0,
                gap_index=None,
                new_start="09:30",
                new_end="10:30",
                new_activity="Updated Break",
                use_staged=False,
                gap_match={"start": "09:00", "end": "10:00", "activity": "Break"},
            )
            self.assertTrue(success, msg=error)

            df = schedule_crud.modality_data[self.modality]["working_hours_df"]
            gap_row = df[df["row_type"] == "gap"].iloc[0]
            self.assertEqual(gap_row["start_time"], time(9, 30))
            self.assertEqual(gap_row["end_time"], time(10, 30))
            self.assertEqual(gap_row["tasks"], "Updated Break")

            success, _, error = schedule_crud._remove_gap_from_schedule(
                self.modality,
                row_index=0,
                gap_index=None,
                use_staged=False,
                gap_match={"start": "09:30", "end": "10:30", "activity": "Updated Break"},
            )
            self.assertTrue(success, msg=error)

            df = schedule_crud.modality_data[self.modality]["working_hours_df"]
            self.assertTrue(df[df["row_type"] == "gap"].empty)
            backup_mock.assert_called()

    def test_update_row_to_gap_enforces_defaults(self) -> None:
        with patch.object(schedule_crud, "backup_dataframe"):
            success, result = schedule_crud._update_schedule_row(
                self.modality,
                row_index=0,
                updates={"row_type": "gap"},
                use_staged=False,
            )
            self.assertTrue(success, msg=result)

            df = schedule_crud.modality_data[self.modality]["working_hours_df"]
            row = df.iloc[0]
            self.assertEqual(row["row_type"], "gap")
            self.assertEqual(row["shift_duration"], 0.0)
            for skill in SKILL_COLUMNS:
                self.assertEqual(row[skill], -1)


if __name__ == "__main__":
    unittest.main()
