# Bug Search Worklist

## Scope Plan
- [x] Review routing/API boundary and data serialization (`routes.py`).
- [x] Review schedule CRUD and gap handling (`data_manager/schedule_crud.py`).
- [x] Review CSV parsing and schedule build logic (`data_manager/csv_parser.py`).
- [x] Review file persistence and backup/restore flow (`data_manager/file_ops.py`).
- [x] Review balancing logic and work-hour calculations (`balancer.py`).
- [x] Review shared utilities/time handling (`lib/utils.py`).
- [x] Review state/task orchestration (`state_manager.py`, `data_manager/scheduled_tasks.py`).
- [x] Review worker roster/skill management (`data_manager/worker_management.py`).
- [x] Review prep/timeline UI logic for data contracts (`static/js/prep_next_day.actions.js`, `static/js/timeline.js`).
- [ ] Review remaining Flask app entrypoints and templates for boundary issues (`app.py`, `templates/`).
- [ ] Review remaining static JS/CSS assets for data contract mismatches (`static/js/*`, `static/*.css`).
- [ ] Review docs/config for mismatches that could drive runtime defects (`docs/*`, `config.yaml`).

## Findings & Fixes
1. **Shift duration truncation for multi-day windows**
   - **Symptom**: Shift duration calculations used `timedelta.seconds`, which drops day information and can undercount durations when a shift window spans midnight or is otherwise more than 24 hours.
   - **Root cause**: `data_manager/schedule_crud.py` computed durations with `(end_dt - start_dt).seconds`, which ignores days.
   - **Fix**: Switched to `.total_seconds()` in all schedule CRUD duration calculations to preserve day information without altering same-day behavior.
   - **Risk**: Low. Same-day shifts are unchanged; only cross-day spans compute correctly.
   - **Suggested tests**: Update a shift to span midnight in prep/live schedule and verify shift_duration and TIME updates.

2. **Indentation error in add-worker duration calculation**
   - **Symptom**: The add-worker path had a mis-indented `if` block, which would raise an `IndentationError` on import and prevent schedule CRUD from loading.
   - **Root cause**: An extra indentation level before the `if end_dt > start_dt:` block in `_add_worker_to_schedule`.
   - **Fix**: Realigned the conditional block to the correct indentation level.
   - **Risk**: Low. This restores valid module parsing and keeps the existing duration logic.
   - **Suggested tests**: Import the app module and add a worker through `/api/live-schedule/add-worker` and `/api/prep-next-day/add-worker`.
