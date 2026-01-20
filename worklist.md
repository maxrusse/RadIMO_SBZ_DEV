# Worklist: Model Gaps as First-Class Child Entities

## Goal
Replace the current “split rows with gap_id” behavior with a clean, first-class gap model that keeps a single shift row and stores gaps as child entities. This enables:
- Editing a worker’s shift as one contiguous entry.
- Adding/removing gaps without destroying the original shift.
- UI that shows a single shift with gap overlays and a gap “X” action.

## Current State (Summary)
- Backend splits a shift into multiple rows when a gap is added (`_add_gap_to_schedule`).
- UI merges rows back for display, but the edit modal uses raw rows, causing split shifts to appear in edit mode.
- No real “remove gap” workflow exists because the original shift row is lost.

## Proposed Model (Target State)
### Data Model
- **Shift** remains a single row in the schedule tables (no splitting).
- **Gap** becomes a child entity referenced by the shift row:
  - `gaps`: list of `{ start, end, activity, id }`
  - Keep `gap_id` only for legacy rows (migration compatibility), or remove after migration.

### Persistence
- `gaps` stored in the schedule row as JSON (object list) only.
- No row duplication, no `gap_id`-linked segments for new edits.

## Backend Changes
### 1) Replace Split Logic in `_add_gap_to_schedule`
- **Current**: adjusts times or splits rows.
- **New**: only updates `gaps` JSON and validates overlap.
  - If gap covers entire shift: **either** reject or mark a “full shift gap” entry (decision required).
  - If gap partially overlaps: clip to shift bounds or reject (decision required).

### 2) Add Gap CRUD Endpoints
- `POST /api/*/add-gap` → append to shift’s `gaps` list.
- `POST /api/*/remove-gap` → remove by `gap_id` or `start/end` match.
- `POST /api/*/update-gap` → edit a gap’s time or type.

### 3) Data Migration Strategy
- For legacy split rows with `gap_id`:
  - Identify groups by `gap_id`.
  - Reconstruct a single shift with:
    - start = earliest start_time
    - end = latest end_time
    - gaps = merged from row.gaps + derived gap between segments
  - Delete additional rows.
- Provide a one-time migration task or a script to run manually.

### 4) Validation Rules
- No gap can start/end outside the shift’s time bounds (clip or error).
- Gap ranges cannot overlap each other.
- Multiple gaps per shift allowed.

## Frontend Changes
### 1) Editing UX
- Edit modal uses the single shift row and renders a **gap list**:
  - Each gap row shows time, type, and an `X` (remove).
  - “Add gap” button opens inline editor or modal.

### 2) Quick Edit Mode
- Instead of showing split rows, show one shift row with gap chips.
- Add “X” on each gap (remove gap).

### 3) Timeline Visualization
- Continue to render the shift with overlays from `gaps` array.
- Remove reliance on “derived gaps” from split segments.

### 4) State Handling
- Update `buildEntriesByWorker` to:
  - Use `gaps` directly from the shift row.
  - Stop merging split shifts for UI (legacy data only).

## Compatibility / Rollout Plan
1. Add new gap CRUD and UI for **new data**.
2. Provide migration utility for existing `gap_id` split data.
3. Remove or disable split logic once migration is done.

## Decisions (Locked)
- **Full-shift gaps** become a **full-time gap entry** (gap wins over shift for ranking/visibility) instead of deleting the shift.
- **Storage**: keep gaps stored **per worker/shift in a concise JSON structure** (no separate table for now). Gap rules must override shift-time calculations (e.g., hours counting) and support a per-gap option for whether the time counts.
- **Legacy CSV split rows**: **no legacy support**; we start clean with the new model and do not migrate split-row data.

## Testing Plan
- Create a shift → add gap in middle → ensure shift remains single row.
- Remove gap → shift returns to continuous timeline.
- Add multiple gaps → ensure no overlap allowed.
- Add overlapping gap → ensure error is returned.
- Full-shift gap → ensure `counts_for_hours=False` and `shift_duration=0`.

---

# Implementation Progress

## Step-Wise Approach

### Step 1: Refactor `_add_gap_to_schedule` — Remove Row Splitting ✅ COMPLETED
**File:** `data_manager/schedule_crud.py:508-650`

**Changes made:**

1. **Case 1 (full-shift gap) — CHANGED:**
   - OLD: Deletes the row
   - NEW: Keeps row, adds gap entry, sets `counts_for_hours=False`, `shift_duration=0.0`
   - Returns `'full_shift_gap'` instead of `'deleted'`

2. **Case 4 (gap in middle) — CHANGED:**
   - OLD: Creates new `gap_id` UUID, splits into two rows linked by `gap_id`
   - NEW: Keeps original shift times, only adds gap to `gaps` JSON array
   - Calculates effective duration (shift minus gap durations)
   - Returns `'gap_added'` instead of `'split'`

3. **Cases 2 & 3 (edge gaps) — KEPT AS-IS:**
   - Still adjust `start_time`/`end_time` for edge gaps
   - Added `is_manual` flag setting for consistency

4. **New helper function added:**
   - `calc_effective_duration(gaps_json, shift_start_dt, shift_end_dt)` — computes working hours minus gap durations

**Frontend updates (`prep_next_day.actions.js`):**
- Updated UI messages: "shift split" → "gap added to shift(s)"
- Updated comments to reflect new behavior

**Schnittstellen verified:**
1. `routes.py:1143-1179` — Just passes through action value, no change needed
2. `prep_next_day.actions.js` — Does NOT check action values, just success; messages updated
3. `csv_parser.py:apply_exclusions_to_shifts` — **NEEDS REVIEW in Step 2** (batch gap import)

### Step 2: Update Delete Logic + CSV Parser ✅ COMPLETED
**Files:**
- `data_manager/schedule_crud.py:468-506` (`_delete_worker_from_schedule`)
- `data_manager/csv_parser.py:188-267` (`apply_exclusions_to_shifts`)

**Changes made:**

1. **CSV Parser refactored (`apply_exclusions_to_shifts`):**
   - OLD: Split shifts into multiple segments with same `gap_id`
   - NEW: Keep shifts as single rows with gaps in `gaps` JSON array
   - Calculates effective duration (shift minus gap durations)
   - Full-shift gaps (gap covers entire shift) set `counts_for_hours=False`

2. **Delete logic KEPT for legacy compatibility:**
   - `_delete_worker_from_schedule` still deletes all rows with matching `gap_id`
   - This handles any legacy split-row data that may exist
   - New data won't have `gap_id` links, so it behaves as single-row delete

3. **Cleanup:**
   - Removed unused `uuid` import from `schedule_crud.py`
   - Removed unused `uuid` import from `csv_parser.py`
   - Removed dead code (`existing_gap_id` variable) from `_add_gap_to_schedule`

4. **Documentation updated:**
   - Updated `docs/WORKFLOW.md` to describe new gap model

### Step 3: Add Gap CRUD Endpoints ✅ COMPLETED
**Files:** `routes.py`, `data_manager/schedule_crud.py`

**New backend functions added (`schedule_crud.py:647-841`):**

1. **`_remove_gap_from_schedule(modality, row_index, gap_index, use_staged)`**
   - Removes a gap by its 0-based index in the gaps array
   - Recalculates `shift_duration` after removal
   - Restores `counts_for_hours=True` if effective duration > 0.1 hours
   - Returns `'gap_removed'` action on success

2. **`_update_gap_in_schedule(modality, row_index, gap_index, new_start, new_end, new_activity, use_staged)`**
   - Updates gap start/end times or activity type
   - Validates gap times (start < end)
   - Validates gap is within shift bounds
   - Recalculates `shift_duration` and `counts_for_hours`
   - Returns `'gap_updated'` action on success

**New API endpoints added (`routes.py:1182-1285`):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/live-schedule/remove-gap` | POST | Remove gap from live shift |
| `/api/prep-next-day/remove-gap` | POST | Remove gap from staged shift |
| `/api/live-schedule/update-gap` | POST | Update gap in live shift |
| `/api/prep-next-day/update-gap` | POST | Update gap in staged shift |

**Request body for remove-gap:**
```json
{
  "modality": "CT",
  "row_index": 5,
  "gap_index": 0
}
```

**Request body for update-gap:**
```json
{
  "modality": "CT",
  "row_index": 5,
  "gap_index": 0,
  "new_start": "10:00",
  "new_end": "11:00",
  "new_activity": "Meeting"
}
```

### Step 4: Add Gap Validation Rules ✅ COMPLETED
**File:** `data_manager/schedule_crud.py`

**New validation helper function (`schedule_crud.py:72-97`):**

```python
def _validate_no_gap_overlap(existing_gaps: list, new_gap: dict, exclude_index: int = -1) -> tuple:
```

- Checks if new gap overlaps with any existing gaps
- Supports `exclude_index` parameter for update operations
- Returns `(False, error_message)` if overlap detected
- Time comparison uses string ordering (HH:MM format)

**Validation integration:**

1. **`_add_gap_to_schedule`** (line 591-595):
   - Validates no overlap before adding new gap
   - Returns error: "Gap overlaps with existing gap (HH:MM-HH:MM)"

2. **`_update_gap_in_schedule`** (line 833-836):
   - Validates no overlap when updating gap (excludes self)
   - Returns error if updated gap would overlap with others

**Existing validations preserved:**
- Gap must be within shift time bounds (already existed)
- Gap start must be before end (already existed)
- Gap clipping to shift boundaries in duration calculation (already existed)

### Step 5: Update Frontend State Handling ✅ COMPLETED
**File:** `static/js/prep_next_day.state.js`

**Analysis:**
- `buildEntriesByWorker()` already uses `gaps` directly from shift rows
- `gap_id` merging logic KEPT for legacy data compatibility (splits old data back together)
- New data: Single row with gaps array → displays correctly
- Legacy data: Multiple rows with same `gap_id` → merges and displays correctly

**No changes required** — existing state handling already supports the new model.

### Step 6: Update Frontend Edit Modal ✅ COMPLETED
**Files:** `static/js/prep_next_day.render.js`, `static/js/prep_next_day.actions.js`

**Changes made:**

1. **Gaps section in edit modal** (`prep_next_day.render.js:607-619`):
   - Added yellow "Gaps" section when shift has gaps
   - Each gap shown as a "chip" with start-end time and activity
   - "×" button on each gap chip for removal

2. **Gap removal handler** (`prep_next_day.actions.js:1081-1128`):
   ```javascript
   async function removeGapFromModal(shiftIdx, gapIdx)
   ```
   - Confirms removal with user
   - Calls `/api/*/remove-gap` for all modalities in the shift
   - Reloads data and re-renders modal on success

**User workflow:**
1. Open edit modal for a worker
2. See "Gaps" section with each gap as a removable chip
3. Click "×" to remove a gap
4. Confirm removal in dialog
5. Gap removed, modal refreshes to show updated timeline

---

## Implementation Summary ✅ COMPLETED

All 6 steps have been successfully implemented. The gap model has been refactored from row-splitting to first-class child entities.

### Key Changes Made:

**Backend (`data_manager/schedule_crud.py`):**
- `_add_gap_to_schedule`: No longer splits rows; stores gaps as JSON child entities
- `_remove_gap_from_schedule`: New function to remove gaps by index
- `_update_gap_in_schedule`: New function to update gap times/activity
- `_validate_no_gap_overlap`: New validation helper for overlap detection
- Removed `uuid` import (no longer creating gap_id for splits)

**Backend (`data_manager/csv_parser.py`):**
- `apply_exclusions_to_shifts`: Refactored to keep single rows with gaps JSON
- Removed `uuid` import

**API (`routes.py`):**
- Added 4 new endpoints: `remove-gap` and `update-gap` for live/staged data

**Frontend (`static/js/prep_next_day.render.js`):**
- Edit modal now shows gaps as removable chips

**Frontend (`static/js/prep_next_day.actions.js`):**
- `removeGapFromModal`: New handler for gap removal from edit modal
- Updated UI messages to reflect new model

**Documentation (`docs/WORKFLOW.md`):**
- Updated to describe new gap model

### Files Modified:
1. `data_manager/schedule_crud.py`
2. `data_manager/csv_parser.py`
3. `routes.py`
4. `static/js/prep_next_day.actions.js`
5. `static/js/prep_next_day.render.js`
6. `docs/WORKFLOW.md`
7. `worklist.md` (this file)

---

## Open Points & Future Work

### Legacy `gap_id` Removal ✅ COMPLETED

**Decision:** Remove ALL legacy `gap_id` code - start clean with new model.

**Cleaned locations:**

| # | File | What Was Removed | Status |
|---|------|------------------|--------|
| 1 | `routes.py` | `gap_id` field from API response | ✅ |
| 2 | `data_manager/schedule_crud.py` | Delete-by-gap_id logic in `_delete_worker_from_schedule` | ✅ |
| 3 | `data_manager/schedule_crud.py` | `gap_id` column initialization in `_add_gap_to_schedule` | ✅ |
| 4 | `data_manager/file_ops.py` | `gap_id` from column order | ✅ |
| 5 | `static/js/prep_next_day.actions.js` | `gap_id` property and merge-by-gap_id logic | ✅ |
| 6 | `static/js/prep_next_day.render.js` | 🔗 linked icon for `gap_id` shifts | ✅ |

**Summary of cleanup:**
- Removed `has_gap_id` check and `gap_id` from API response
- Simplified delete logic to single-row delete (no gap_id chain delete)
- Removed `gap_id` column initialization
- Removed `gap_id` from DataFrame column order
- Removed `gap_id` property from entry/shift objects
- Removed `sameGapId` merge condition (now only merges same task with gap)
- Removed 🔗 linked icon display

### Comments Updated ✅
- `prep_next_day.actions.js:750` — Updated to "Merge consecutive shifts with same task and gap between"
- Removed all gap_id-related comments

### Testing Plan ✅ Fixed
Updated Testing Plan (line 81-86) to remove legacy migration test case and add:
- Overlap validation test
- Full-shift gap test

### Adjunct Files NOT Modified (Already Compatible)
These files already handle the new gap model correctly:
- `static/js/timeline.js` — Renders gaps from `gaps` array, no changes needed
- `config.py` — No gap-related config
- No JSON config files reference gaps

### Potential Enhancements (Not Required)
1. **Gap editing UI** — Currently only removal is supported; could add inline time editing
2. **Gap type dropdown** — Pre-populate with configured gap activities from `TASK_ROLES`
3. **Visual gap preview** — Show gap effect on timeline before confirming
