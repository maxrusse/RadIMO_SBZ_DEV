# Bug Search Worklist

**Project:** RadIMO Cortex
**Started:** 2026-01-20
**Status:** Phase 1-7 Complete

---

## Phase 1: API Boundaries and Route Handlers (High Risk)
Critical paths where user input enters the system.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| routes.py | 1690 | [x] Complete | See findings BUG-001, BUG-002 |

## Phase 2: Core Business Logic (High Risk)
Load balancing and scheduling logic where calculation errors can cause incorrect assignments.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| balancer.py | 592 | [x] Complete | Solid - proper division guards, lock documentation |
| data_manager/schedule_crud.py | 949 | [x] Complete | See note on exception handling |

## Phase 3: Data Handling (Medium Risk)
CSV parsing, file operations, state persistence - data corruption and parsing errors.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| data_manager/csv_parser.py | 633 | [x] Complete | See finding BUG-003 |
| data_manager/file_ops.py | 656 | [x] Complete | See finding BUG-004 |
| data_manager/worker_management.py | 541 | [x] Complete | See finding BUG-005 |
| data_manager/state_persistence.py | 93 | [ ] Pending | To be reviewed |

## Phase 4: Configuration and State (Medium Risk)
Config loading and state management.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| config.py | 432 | [x] Complete | Solid - defensive type coercion |
| state_manager.py | 337 | [x] Complete | Solid - proper singleton pattern |

## Phase 5: Scheduled Tasks and Utilities (Lower Risk)
Background jobs and helper functions.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| data_manager/scheduled_tasks.py | 235 | [ ] Pending | |
| lib/utils.py | 199 | [ ] Pending | |
| lib/usage_logger.py | 215 | [ ] Pending | |

## Phase 6: Application Entry Points (Lower Risk)
Flask app initialization and server config.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| app.py | 100 | [ ] Pending | |
| gunicorn_config.py | 39 | [ ] Pending | |

## Phase 7: Frontend JavaScript (Medium Risk)
Client-side logic, async operations, event handling.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| static/js/prep_next_day.actions.js | 2716 | [x] Complete | See finding BUG-006 |
| static/js/prep_next_day.render.js | 980 | [ ] Pending | |
| static/js/timeline.js | 628 | [ ] Pending | |
| static/js/worker_load_monitor.js | 471 | [ ] Pending | |
| static/js/prep_next_day.state.js | 330 | [x] Complete | Solid - proper escapeHtml |
| static/js/timetable.js | 206 | [ ] Pending | |
| static/js/prep_next_day.config.js | 63 | [ ] Pending | |

## Phase 8: HTML Templates (Lower Risk)
Template logic, dynamic content, accessibility.

| File | Status | Notes |
|------|--------|-------|
| templates/index.html | [ ] Pending | |
| templates/index_by_skill.html | [ ] Pending | |
| templates/prep_next_day.html | [ ] Pending | |
| templates/skill_roster.html | [ ] Pending | |
| templates/timetable.html | [ ] Pending | |
| templates/upload.html | [ ] Pending | |
| templates/worker_load_monitor.html | [ ] Pending | |
| templates/login.html | [ ] Pending | |
| templates/base.html | [ ] Pending | |
| templates/partials/*.html | [ ] Pending | |

---

## Findings Summary

| ID | Severity | File | Description | Status |
|----|----------|------|-------------|--------|
| BUG-001 | Medium | routes.py | Race condition in `_ensure_next_workday_preloaded()` - reads `last_preload_date` inside lock but performs preload outside | Documented |
| BUG-002 | Low | routes.py | Invalid modality in timetable route causes KeyError when accessing `modality_data[mod]` | Documented |
| BUG-003 | Low | csv_parser.py | Gap processing may overwrite gaps from `apply_exclusions_to_shifts()` at line 601 | Documented |
| BUG-004 | Low | file_ops.py | `backup_dataframe()` does not acquire lock before modifying `d['last_modified']` | Documented |
| BUG-005 | Low | worker_management.py | Non-atomic roster update: `clear()` then `update()` in `load_worker_skill_json()` | Documented |
| BUG-006 | Low | prep_next_day.actions.js | Missing radix in `parseInt()` calls at lines 175, 230, 251 | Documented |

---

## Detailed Findings

### BUG-001: Race condition in preload (routes.py:145-164)

**Symptom:** Potential double-preload of next workday data in concurrent requests.

**Root cause:** The function reads `last_preload_date` inside the lock (line 148-155) but performs the actual preload operation outside the lock (line 162). Two concurrent requests could both see an outdated `last_preload_date` and trigger redundant preloads.

**Code path:**
```python
def _ensure_next_workday_preloaded():
    global last_preload_date
    with lock:  # Lock acquired
        if last_preload_date == workday:
            return
        last_preload_date = workday  # Set inside lock
    # Lock released - potential race here
    preload_next_workday(workday)  # Called outside lock
```

**Risk:** Low - Preload is idempotent, worst case is wasted work.

**Proposed fix:** Keep preload inside lock or use double-check pattern.

---

### BUG-002: Invalid modality KeyError (routes.py:341-349)

**Symptom:** `KeyError` when accessing timetable with invalid modality parameter.

**Root cause:** The `modality` query parameter is not validated against `allowed_modalities` before use.

**Code path:**
```python
modality = request.args.get('modality', 'all')
target_modalities = allowed_modalities if modality == 'all' else [modality]
for mod in target_modalities:
    df = modality_data[mod]['working_hours_df']  # KeyError if mod invalid
```

**Risk:** Low - Only affects admin users with malformed URLs.

**Proposed fix:** Validate modality or use `.get()` with default.

---

### BUG-003: Gap overwrite in csv_parser.py (lines 594-601)

**Symptom:** Worker exclusion gaps may overwrite gaps set by `apply_exclusions_to_shifts()`.

**Root cause:** Third pass rebuilds gaps from `worker_exclusions` and assigns to `shift['gaps']`, potentially overwriting previously set gaps.

**Risk:** Low - Affects edge case of overlapping exclusion types.

---

### BUG-004: Unlocked backup modification (file_ops.py:425)

**Symptom:** Concurrent backup operations could interfere.

**Root cause:** `backup_dataframe()` modifies `d['last_modified']` and writes files without acquiring the state lock.

**Risk:** Very low - Backup conflicts are unlikely in practice.

---

### BUG-005: Non-atomic roster update (worker_management.py:116-117)

**Symptom:** Other threads could see empty roster between `clear()` and `update()`.

**Root cause:** The sequence `worker_skill_json_roster.clear()` followed by `.update(data)` is not atomic.

**Risk:** Very low - Roster is loaded at startup and on admin operations.

---

### BUG-006: Missing parseInt radix (prep_next_day.actions.js)

**Symptom:** Potential incorrect parsing if value starts with "0".

**Locations:**
- Line 175: `parseInt(row)` → should be `parseInt(row, 10)`
- Line 230: `parseInt(row)` → should be `parseInt(row, 10)`
- Line 251: `parseInt(gidx)`, `parseInt(sidx)` → need radix 10

**Risk:** Very low - Row indices are unlikely to start with "0" in problematic ways.

**Proposed fix:** Add radix parameter to all `parseInt()` calls.

---

## Code Quality Notes (Not Bugs)

1. **routes.py:** Many routes use `data = request.json` without null check. If client sends empty body, this returns `None` and subsequent `.get()` calls will fail. However, Flask's `request.json` returns `None` gracefully, and `.get()` on `None` raises `AttributeError`. This is a minor robustness issue.

2. **schedule_crud.py:** `_parse_gap_list()` catches all exceptions and returns empty list. This could mask parsing bugs but is acceptable for fault tolerance.

3. **state_manager.py:** Properties return direct references to internal dicts. This is intentional for performance but requires callers to acquire the lock for multi-step operations.

4. **JavaScript:** Good use of `escapeHtml()` for XSS prevention. Async error handling is properly implemented with try/catch.

---

## Next Steps

1. Review remaining Phase 5-8 files
2. Consider adding guards for BUG-001 and BUG-002 (low priority)
3. Add radix to JavaScript parseInt calls (trivial fix)
