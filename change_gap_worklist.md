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
- [ ] Add `row_type` column to working hours DataFrames (defaults to `shift` when missing).
- [ ] Ensure CSV export/import includes `row_type`.
- [ ] Update file column order to include `row_type` (remove `gaps`).
### 2) CSV parsing: produce gap rows
- [ ] In `build_working_hours_from_medweb`, replace “apply gaps to shifts” logic with explicit row creation:
  - For each gap rule, add a `gap` row (per gap time range).
  - For embedded shift rule gaps, add separate `gap` rows.
  - Shifts remain unchanged (no `gaps` JSON).
- [ ] Remove `apply_exclusions_to_shifts` usage and the “third pass” logic that overwrites gaps inside shifts.

### 3) CRUD: gap add/update/remove as row operations
- [ ] Replace `_add_gap_to_schedule` to insert a new `gap` row, not update a shift row.
- [ ] Replace `_remove_gap_from_schedule` to delete a gap row.
- [ ] Replace `_update_gap_in_schedule` to edit a gap row’s times/activity.
- [ ] Ensure row selection and UI wiring handles “gap rows” directly.

### 4) Hour calculation updates
- [ ] Replace `_calc_effective_duration_from_gaps` usage with a new overlap-based function:
  - For each worker/day, compute effective working minutes by subtracting merged gap intervals.
- [ ] Ensure `shift_duration` is recomputed based on gap overlaps for each shift row (or computed on demand).
- [ ] Ensure `counts_for_hours` logic is applied after gap subtraction.

### 5) Frontend model: treat gaps as first-class rows
- [ ] Update `buildEntriesByWorker` to build two collections:
  - `shiftEntries` from `row_type=shift` rows.
  - `gapEntries` from `row_type=gap` rows.
- [ ] Remove merge logic that pulls `row.gaps` into shift entries.
- [ ] Timeline rendering: overlay gap bars onto shift bars by clipping gaps into shift ranges.
- [ ] Editing: update edit modal flows to edit/delete gap rows directly.

### 6) API contracts
- [ ] Update `/api/*/add-gap`, `/remove-gap`, `/update-gap` endpoints to operate on gap rows.
- [ ] Update server responses to include `row_type` and avoid `gaps` field.
- [ ] Ensure any downstream consumers handle the new schema.

### 7) Legacy code removal
- [ ] Remove `gaps` JSON column handling in:
  - CSV parser
  - schedule_crud
  - frontend data assembly
  - any UI gap merge helpers
- [ ] Delete helpers specific to embedded gaps if no longer used.

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
- Hour calculations match “gap wins” semantics with multiple overlaps.
- UI timeline shows gap overlays without embedding gap data in shift rows.
