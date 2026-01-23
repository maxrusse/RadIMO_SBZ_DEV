import csv
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from config import SKILL_COLUMNS, allowed_modalities
from data_manager import schedule_crud
from data_manager import worker_management
from data_manager.csv_parser import build_working_hours_from_medweb


class TestDayPlanIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.modality = allowed_modalities[0]
        schedule_crud.modality_data[self.modality]["working_hours_df"] = pd.DataFrame()

    def test_csv_import_matches_edit_flow(self) -> None:
        target_date = datetime(2026, 1, 23)
        worker_name = "Alice (A1)"
        skill_key = SKILL_COLUMNS[0]
        skill_override_key = f"{skill_key}_{self.modality}"

        config = {
            "medweb_mapping": {
                "columns": {
                    "date": "Datum",
                    "activity": "Beschreibung der Aktivität",
                    "employee_name": "Name des Mitarbeiters",
                    "employee_code": "Code des Mitarbeiters",
                },
                "rules": [
                    {
                        "match": "Shift A",
                        "type": "shift",
                        "label": "Shift A",
                        "times": {"default": "08:00-12:00"},
                        "skill_overrides": {skill_override_key: 1},
                    },
                    {
                        "match": "Shift B",
                        "type": "shift",
                        "label": "Shift B",
                        "times": {"default": "10:00-14:00"},
                        "skill_overrides": {skill_override_key: 1},
                    },
                    {
                        "match": "Break",
                        "type": "gap",
                        "label": "Break",
                        "times": {"default": "09:00-09:30"},
                        "counts_for_hours": False,
                    },
                ],
            },
            "balancer": {"hours_counting": {"shift_default": True, "gap_default": False}},
            "worker_roster": {},
        }

        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(csv_path, mode="w", encoding="utf-8", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        "Datum",
                        "Beschreibung der Aktivität",
                        "Name des Mitarbeiters",
                        "Code des Mitarbeiters",
                    ]
                )
                writer.writerow(["23.01.2026", "Shift A", "Alice", "A1"])
                writer.writerow(["23.01.2026", "Shift B", "Alice", "A1"])
                writer.writerow(["23.01.2026", "Break", "Alice", "A1"])

            worker_management.worker_skill_json_roster.clear()
            with patch("data_manager.worker_management.load_worker_skill_json", return_value={}):
                csv_result = build_working_hours_from_medweb(csv_path, target_date, config)

            csv_df = csv_result[self.modality]

            with patch.object(schedule_crud, "backup_dataframe"):
                base_skills = {skill: 0 for skill in SKILL_COLUMNS}
                base_skills[skill_key] = 1
                for worker_data in [
                    {
                        "PPL": worker_name,
                        "start_time": "08:00",
                        "end_time": "12:00",
                        "tasks": "Shift A",
                        "Modifier": 1.0,
                        "row_type": "shift",
                        "counts_for_hours": True,
                        **base_skills,
                    },
                    {
                        "PPL": worker_name,
                        "start_time": "10:00",
                        "end_time": "14:00",
                        "tasks": "Shift B",
                        "Modifier": 1.0,
                        "row_type": "shift",
                        "counts_for_hours": True,
                        **base_skills,
                    },
                    {
                        "PPL": worker_name,
                        "start_time": "09:00",
                        "end_time": "09:30",
                        "tasks": "Break",
                        "Modifier": 1.0,
                        "row_type": "gap",
                        "counts_for_hours": False,
                    },
                ]:
                    success, _, error = schedule_crud._add_worker_to_schedule(
                        self.modality,
                        worker_data,
                        use_staged=False,
                    )
                    self.assertTrue(success, msg=error)

            edit_df = schedule_crud.modality_data[self.modality]["working_hours_df"]

            cols = [
                "PPL",
                "row_type",
                "start_time",
                "end_time",
                "tasks",
                "Modifier",
                "counts_for_hours",
                "shift_duration",
                *SKILL_COLUMNS,
            ]

            csv_norm = csv_df[cols].copy()
            edit_norm = edit_df[cols].copy()

            sort_cols = ["row_type", "start_time", "end_time", "tasks"]
            csv_norm = csv_norm.sort_values(by=sort_cols).reset_index(drop=True)
            edit_norm = edit_norm.sort_values(by=sort_cols).reset_index(drop=True)
            csv_norm["shift_duration"] = csv_norm["shift_duration"].round(4)
            edit_norm["shift_duration"] = edit_norm["shift_duration"].round(4)

            assert_frame_equal(csv_norm, edit_norm, check_dtype=False)
        finally:
            os.unlink(csv_path)


if __name__ == "__main__":
    unittest.main()
