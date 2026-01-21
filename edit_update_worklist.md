# Edit Popup Replan Worklist

## Goal
Create a dedicated **edit popup planning state** that is fully independent from the live merged view. The modal should operate on a stable snapshot of a worker’s shifts/gaps, allow edits without mid-edit merges, and then **overwrite the worker’s schedule** on apply.

---

## Problems Observed (Current State)
- The modal edits are applied **row-by-row** and immediately re-merged after each change, which can reshuffle gaps and shift segments mid-edit.
- Gaps are derived from merged data and clipped to shift windows, which makes in-modal edits feel unstable because the source data itself is recomputed.
- Updates are pushed **per modality row**, but the user is conceptually editing a **single worker plan**.

## Current Code Touchpoints (Map Before Refactor)
### Modal Rendering + State
- `renderEditModalContent()` in `static/js/prep_next_day.render.js` builds the modal UI and injects time inputs, gap chips, and skill tables.
- Modal data comes from `getModalShifts(group)` and `group.modalShiftsArray` computed in `static/js/prep_next_day.actions.js`.
- Gaps are **clipped** to shift boundaries and enriched with `originalStart/originalEnd` during `buildEntriesByWorker()` in `static/js/prep_next_day.actions.js`.

### Live Update Calls (to be replaced by Apply)
- Shift updates: `updateShiftFromModal()` -> `POST /api/*/update-row` (per modality row).
- Gap updates: `updateGapDetailsFromModal()` -> `POST /api/*/update-gap` (per modality row).
- Gap removal: `removeGapFromModal()` -> `POST /api/*/remove-gap` (per modality row).
- Gap addition: `addShiftFromModal()` uses `POST /api/*/add-gap` when a gap overlaps a shift, otherwise creates new rows.

### Merge/Clip Logic (drives instability)
- `buildEntriesByWorker()` constructs `group.modalShiftsArray` and `group.shiftsArray` by merging shifts, clipping gaps, and merging modalities.
- Consecutive shifts with same task are merged into `timeSegments`, which affects gap display and edit targets.

### Implications for the Redesign
- The new **EditPlan** must be created **before** any merges/clips and stored separately, otherwise edits still fight the merge pipeline.
- Applying the plan should replace worker rows **after** building the full worker schedule, not per field.

---

## Target Design
### 1) Dedicated “Edit Plan” State
- **Snapshot**: On modal open, create a worker-level plan snapshot:
  - `worker`
  - `shifts[]`: `task`, `start_time`, `end_time`, `modifier`, `counts_for_hours`, `skillsByModality`
  - `gaps[]`: `activity`, `start`, `end`, `counts_for_hours`, `scope` (e.g., applies to all modalities or specific ones)
- **No merging during edits**: Keep shifts/gaps separate while in the modal.
- **Apply**: One explicit “Apply changes” action replaces the worker’s schedule.

### 2) Controlled Merge Pipeline
- **Before apply**: Use stable, editable records, not auto-clipped gap projections.
- **On apply**: Build final rows for each modality using the single source of truth.
  - Expand `shifts[]` into modality rows.
  - Inject gaps into shift rows as needed.
  - Overwrite existing rows for that worker.

### 3) Plan-First Data Model (New)
- `EditPlan`
  - `worker`
  - `shifts[]`
    - `id`
    - `task`
    - `start_time` / `end_time`
    - `modifier`
    - `counts_for_hours`
    - `skillsByModality` (map of modality -> skill map)
  - `gaps[]`
    - `id`
    - `activity`
    - `start` / `end`
    - `counts_for_hours`
    - `appliesTo` (`all` | `[modality]` | `shiftId`)
  - `ui`
    - `activeShiftId`
    - `dirty` flag

---

## Required UI Changes
### Modal Structure
- **Tab 1: Shifts**
  - List shifts as independent cards (no auto-merge).
  - Add/remove shifts without immediate backend calls.
- **Tab 2: Gaps**
  - Separate list of gaps with edit fields.
  - Option to target a shift or apply globally.
- **Apply/Cancel**
  - “Apply changes” sends plan as a single payload.
  - “Cancel” discards draft state.

### Inline Editing
- Remove live-per-field updates in modal.
- Use **draft state** and update on Apply only.

---

## Required Backend/API Changes
### New API
- `POST /api/.../edit-plan/apply`
  - Payload: full `EditPlan` data for a worker.
  - Server rebuilds rows for all modalities and replaces existing worker rows.

### Existing API Changes
- Avoid calling `update-row` / `update-gap` for modal edits.
- Existing quick-edit mode can remain as-is.

---

## Implementation Steps
1. **Define EditPlan object** in front-end state.
2. **Render modal** from EditPlan only (no recomputation from merged data mid-edit).
3. **Remove direct update calls** from modal inputs; store draft locally.
4. **Add Apply action** to send full plan.
5. **Backend apply handler**: delete existing worker rows and insert new rows computed from the plan.
6. **Rebuild worker view** after apply (single reload).

---

## Edge Cases & Rules
- Ensure gaps outside shift windows are valid (show warning if not overlapping a shift and `appliesTo` is a shift).
- For “global gaps”, apply to all matching shifts by time overlap.
- Preserve `counts_for_hours` semantics for both shifts and gaps.
- Enforce time validation at Apply time, not per keystroke.

---

## Checklist
- [x] New EditPlan data model and draft state
- [x] Modal UI refactor to use EditPlan
- [x] Apply/Cancel flow
- [x] Backend apply endpoint
- [x] Remove modal live-update calls
- [x] Document user flow in UI (hint text)
