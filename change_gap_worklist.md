# Change plan: Separate gaps from shifts (gap wins) — detailed worklist

## Goals
- Separate gaps from shifts as independent schedule rows (no parent/child JSON).
- Gaps always win over shifts for availability and hour calculations.
- Support multiple shifts and multiple gaps per worker per day, including overlaps.
- Remove legacy code paths that embed gaps inside shift rows.

## Core data model decisions
- Introduce an explicit `row_type` (or `entry_type`) field on all rows:
  - `shift` for working shifts.
  - `gap` for unavailability/breaks.
- Keep `start_time`, `end_time`, `tasks`, `counts_for_hours`, `Modifier`, and skills in both.
- For gaps, skills can be `-1` (or a minimal schema) to preserve UI expectations.
- Deprecate the `gaps` JSON column and any logic that reads/writes embedded gaps.

## Overlap & hour calculation rules (authoritative)
- For a given worker and day:
  1. Build a list of all shift time windows.
  2. Build a list of all gap time windows.
  3. Normalize each list by merging internal overlaps (within shifts and within gaps).
  4. Subtract the union of gap intervals from each shift interval.
  5. Effective working time is the sum of remaining shift segments where `counts_for_hours=true`.
- A gap “wins” by removing time from any overlapping shift segments.
- Full overlap means a shift can end up with zero effective duration (treated as non-working time).

## Detailed implementation worklist

### 1) Data model & persistence
- [x] Add `row_type` column to working hours DataFrames (defaults to `shift` when missing).
  - Implemented via `_ensure_row_type_column()` in schedule_crud.py
- [x] Ensure CSV export/import includes `row_type`.
  - csv_parser.py creates rows with explicit `row_type`
- [x] Update file column order to include `row_type` (remove `gaps`).
  - No `gaps` column is written to DataFrames

### 2) CSV parsing: produce gap rows
- [x] In `build_working_hours_from_medweb`, replace "apply gaps to shifts" logic with explicit row creation:
  - For each gap rule, add a `gap` row (per gap time range). ✓
  - For embedded shift rule gaps, add separate `gap` rows. ✓
  - Shifts remain unchanged (no `gaps` JSON). ✓
- [x] Remove `apply_exclusions_to_shifts` usage and the "third pass" logic that overwrites gaps inside shifts.
  - Function removed; dead export cleaned up.

### 3) CRUD: gap add/update/remove as row operations
- [x] Replace `_add_gap_to_schedule` to insert a new `gap` row, not update a shift row.
- [x] Replace `_remove_gap_from_schedule` to delete a gap row.
- [x] Replace `_update_gap_in_schedule` to edit a gap row's times/activity.
- [x] Ensure row selection and UI wiring handles "gap rows" directly.

### 4) Hour calculation updates
- [x] Replace `_calc_effective_duration_from_gaps` usage with a new overlap-based function:
  - Implemented via `_recalculate_worker_shift_durations()` using `_subtract_intervals()`
- [x] Ensure `shift_duration` is recomputed based on gap overlaps for each shift row (or computed on demand).
- [x] Ensure `counts_for_hours` logic is applied after gap subtraction.

### 5) Frontend model: treat gaps as first-class rows
- [x] Update `buildEntriesByWorker` to build two collections:
  - Uses `row_type === 'gap'` to identify gap rows
  - Collects gaps in `allGaps` array per worker
- [x] Remove merge logic that pulls `row.gaps` into shift entries.
  - No DataFrame `gaps` column; frontend `shift.gaps` is a view-model for UI display
- [x] Timeline rendering: overlay gap bars onto shift bars by clipping gaps into shift ranges.
- [x] Editing: update edit modal flows to edit/delete gap rows directly.

### 6) API contracts
- [x] Update `/api/*/add-gap`, `/remove-gap`, `/update-gap` endpoints to operate on gap rows.
- [x] Update server responses to include `row_type` and avoid `gaps` field.
- [x] Ensure any downstream consumers handle the new schema.

### 7) Legacy code removal
- [x] Remove `gaps` JSON column handling in:
  - CSV parser: No `gaps` column written
  - schedule_crud: Gap operations are row-based
  - frontend data assembly: Uses `row_type` as primary indicator
  - any UI gap merge helpers: `mergeUniqueGaps` is for UI display deduplication only
- [x] Delete helpers specific to embedded gaps if no longer used.
  - `apply_exclusions_to_shifts` removed

### 8) Testing plan (must cover overlaps)
- [ ] Unit tests for overlap logic:
  - Multiple gaps overlapping one shift.
  - Multiple shifts overlapping one gap.
  - Gaps overlapping each other (merge behavior).
  - Shifts overlapping each other (existing “later wins” logic may need review).
- [ ] Integration tests for CRUD gap operations:
  - Add gap → row created
  - Update gap → row edited
  - Remove gap → row deleted
- [ ] UI sanity checks for timeline rendering with multiple gaps/shifts.

## Overlap algorithm details (recommended)
- Represent intervals as minutes since midnight.
- Merge intervals by sorting and folding.
- Subtract gaps from each shift interval to produce remaining segments.
- Total effective minutes = sum of remaining segments for shift rows.

## Risks & mitigations
- **Risk:** Existing UI relies on `is_gap_entry` detection from task names.
  - **Mitigation:** Use `row_type` as the primary indicator and keep task labels for display only.
- **Risk:** Overlap logic may differ from current “later shift wins.”
  - **Mitigation:** Keep existing shift overlap resolution but apply gap subtraction after shift resolution.
## Completion criteria
- No code path writes or reads `gaps` JSON on shift rows.
- Gap operations are row-based and fully independent.
- Hour calculations match "gap wins" semantics with multiple overlaps.
- UI timeline shows gap overlays without embedding gap data in shift rows.

---

## Additional cleanup notes (2026-01-23)

### Cleanup completed

1. **Removed legacy `is_gap_entry` fallback patterns in `prep_next_day.render.js`**
   - Lines 300, 536-538: Previously used fallback `isGapTask(shift.task)` when `is_gap_entry` was undefined
   - Since `is_gap_entry` is now reliably set from `row_type` in `buildEntriesByWorker`, the fallback is unnecessary
   - Simplified to: `const isGapRow = Boolean(shift.is_gap_entry);`

2. **Removed unused `shiftIdx` parameter from `onQuickGap30` function**
   - `prep_next_day.actions.js`: Function signature changed from `onQuickGap30(tab, gIdx, shiftIdx, durationMinutes)` to `onQuickGap30(tab, gIdx, durationMinutes)`
   - Updated callers in `prep_next_day.actions.js` and `prep_next_day.render.js`
   - Parameter was documented as "unused, for compatibility" and always passed as 0

### Items reviewed and kept

1. **`is_gap_entry` field in view model** — Intentionally kept
   - Derived from `row_type` in `buildEntriesByWorker` at line 632
   - Propagated through the shift/entry objects for use in rendering
   - Serves as a computed boolean property for easier conditionals in UI code

2. **`shift.gaps` array in view model** — Intentionally kept
   - This is a UI-only view model array for rendering gap overlays visually within shift rows
   - NOT persisted to database; computed from separate gap rows for display purposes
   - Used by `timeline.js` and rendering code to show gaps inline with shifts

3. **`isGapTask()` function** — Intentionally kept
   - Still used in multiple places for config-based gap detection:
     - Finding gap task names in multi-task entries (line 586)
     - Filtering non-gap shifts for display logic (lines 938, 941)
     - Determining gap type when adding/updating entries (lines 1468, 2229)
   - Reads from `TASK_ROLES` config to identify gap task names

### Architecture notes

- **Data flow**: Backend uses `row_type` column → Frontend derives `is_gap_entry` in `buildEntriesByWorker` → Render code uses `is_gap_entry` boolean
- **Gap visualization**: Separate gap rows are collected in `allGaps`, then clipped into shift time ranges for the `shift.gaps` view model used by timeline rendering
- **No redundancy**: The `is_gap_entry` boolean and `shift.gaps` array serve distinct purposes (row identification vs. visual overlay)

---

## Additional cleanup notes (2026-01-23, continued)

### Aligned gap handling to new standalone row model

3. **Simplified `onQuickGap30` (quick break NOW feature)**
   - Removed legacy "overlapping shifts" detection logic
   - Previously: looped through overlapping shifts/modalities and called `callAddGap` for each (could create duplicates)
   - Now: always creates a single standalone gap row via `/api/*/add-worker` with `row_type: 'gap'`
   - Confirmation message simplified (no longer mentions "add to shifts" vs "create gap entry")

4. **Simplified add-worker modal gap handling (`addShiftFromModal`)**
   - Removed legacy overlap checking that called add-gap API for each overlapping shift
   - Now: always creates standalone gap rows with `row_type: 'gap'`
   - Fixed missing `row_type: 'gap'` that was previously unset in some code paths

5. **Simplified add-worker modal batch processing (`executeAddWorkerModal`)**
   - Removed overlap detection loop for gap tasks
   - Gap tasks now always create standalone rows with `row_type: 'gap'`
   - Removed unused `gapEndpoint` variable

6. **Removed unused `callAddGap` helper function**
   - Was a wrapper for the add-gap API endpoint
   - No longer needed since all gap creation now uses add-worker endpoint with `row_type: 'gap'`

7. **Consolidated `_subtract_intervals` function**
   - Previously duplicated in `schedule_crud.py` and `csv_parser.py`
   - Moved to `lib/utils.py` as `subtract_intervals()` with generic type hints
   - Works with both integer (minutes) and datetime intervals
   - Both modules now import from shared location

### API endpoint status

The add-gap/remove-gap/update-gap endpoints are still used for:
- **remove-gap**: Deleting gap rows from the edit modal
- **update-gap**: Editing gap times/properties from the edit modal

The add-gap endpoint is no longer needed for creating gaps (use add-worker with `row_type: 'gap'` instead) but remains for backward compatibility.
