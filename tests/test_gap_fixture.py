import json
from datetime import date
from pathlib import Path

from config import SKILL_COLUMNS
from lib.utils import normalize_skill_value
from data_manager.schedule_crud import build_day_plan_rows


def test_gap_fixture_builds_day_plan_rows() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "gap_fixture.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    target_date = date.fromisoformat(payload["date"])
    built = build_day_plan_rows(payload["rows"], target_date)

    assert len(built) == 5
    assert all(row["PPL"] == "Fixture Worker" for row in built)

    shift_times = [
        row["TIME"]
        for row in built
        if row["row_type"] not in {"gap", "gap_segment"}
    ]
    assert shift_times == ["08:00-09:30", "10:00-12:00", "13:00-15:00"]


def test_shift_segments_preserve_skill_values() -> None:
    if not SKILL_COLUMNS:
        return
    skill_name = SKILL_COLUMNS[0]
    rows = [
        {
            "PPL": "Skill Worker",
            "row_type": "shift",
            "start_time": "08:00",
            "end_time": "12:00",
            skill_name: 1,
        },
        {
            "PPL": "Skill Worker",
            "row_type": "gap",
            "start_time": "09:00",
            "end_time": "10:00",
        },
    ]

    built = build_day_plan_rows(rows, date(2026, 1, 23))
    segment_skills = [
        row[skill_name]
        for row in built
        if row["row_type"] not in {"gap", "gap_segment"}
    ]
    expected_skill = normalize_skill_value(1)

    assert segment_skills == [expected_skill, expected_skill]
