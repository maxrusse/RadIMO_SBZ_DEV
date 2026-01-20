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
- Load legacy split data → migration yields one row with correct gaps.
