# Bug Search Worklist

**Project:** RadIMO Cortex
**Started:** 2026-01-20
**Status:** ALL PHASES COMPLETE

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
| data_manager/state_persistence.py | 93 | [x] Complete | Clean - proper TOCTOU handling with try/except |

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
| data_manager/scheduled_tasks.py | 235 | [x] Complete | See finding BUG-007 |
| lib/utils.py | 199 | [x] Complete | See finding BUG-008 |
| lib/usage_logger.py | 215 | [x] Complete | See finding BUG-009 |

## Phase 6: Application Entry Points (Lower Risk)
Flask app initialization and server config.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| app.py | 100 | [x] Complete | See finding BUG-010 |
| gunicorn_config.py | 39 | [x] Complete | See finding BUG-011 (CRITICAL) |

## Phase 7: Frontend JavaScript (Medium Risk)
Client-side logic, async operations, event handling.

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| static/js/prep_next_day.actions.js | 2716 | [x] Complete | See finding BUG-006 |
| static/js/prep_next_day.render.js | 980 | [x] Complete | Solid - good escapeHtml usage |
| static/js/timeline.js | 628 | [x] Complete | Solid - clean IIFE module pattern |
| static/js/worker_load_monitor.js | 471 | [x] Complete | Solid - good structure |
| static/js/prep_next_day.state.js | 330 | [x] Complete | Solid - proper escapeHtml |
| static/js/timetable.js | 206 | [x] Complete | Solid - uses shared TimelineChart |
| static/js/prep_next_day.config.js | 63 | [x] Complete | Config parsing only |

## Phase 8: HTML Templates (Lower Risk)
Template logic, dynamic content, accessibility.

| File | Status | Notes |
|------|--------|-------|
| templates/base.html | [x] Complete | Clean - minimal base template |
| templates/login.html | [x] Complete | Clean - proper Jinja escaping |
| templates/prep_next_day.html | [x] Complete | Clean - uses tojson for safe JSON |
| Other templates | [x] Complete | Follow same patterns |

---

## Findings Summary

| ID | Severity | File | Description | Status |
|----|----------|------|-------------|--------|
| BUG-001 | Medium | routes.py | Race condition in `_ensure_next_workday_preloaded()` | Documented |
| BUG-002 | Low | routes.py | Invalid modality KeyError in timetable route | Documented |
| BUG-003 | Low | csv_parser.py | Gap processing may overwrite earlier gaps | Documented |
| BUG-004 | Low | file_ops.py | `backup_dataframe()` unlocked modification | Documented |
| BUG-005 | Low | worker_management.py | Non-atomic roster update | Documented |
| BUG-006 | Low | prep_next_day.actions.js | Missing radix in `parseInt()` calls | **FIXED** |
| BUG-007 | Very Low | scheduled_tasks.py | `cleared_modalities` always empty (dead code) | Documented |
| BUG-008 | Very Low | utils.py | `validate_excel_structure()` side effect | Documented |
| BUG-009 | Very Low | usage_logger.py | `scheduled_time` defined but never used | Documented |
| BUG-010 | Low | app.py | Unused BackgroundScheduler | Documented |
| BUG-011 | **HIGH** | gunicorn_config.py | Placeholder path `/xxxx/gunicorn.log` | **FIXED** |

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

### BUG-006: Missing parseInt radix (prep_next_day.actions.js) - FIXED

**Symptom:** Potential incorrect parsing if value starts with "0".

**Locations:**
- Line 175: `parseInt(row)` -> `parseInt(row, 10)`
- Line 230: `parseInt(row)` -> `parseInt(row, 10)`
- Line 251: `parseInt(gidx)`, `parseInt(sidx)` -> need radix 10

**Risk:** Very low - Row indices are unlikely to start with "0" in problematic ways.

**Fix applied:** Added radix parameter to all `parseInt()` calls.

---

### BUG-007: Dead code in scheduled_tasks.py (line 226)

**Symptom:** `cleared_modalities` variable is always empty.

**Root cause:** Variable is initialized at line 181 as `cleared_modalities = []` but never populated. It is returned in the result dict but is always empty.

**Risk:** Very low - Does not affect functionality, just dead code.

---

### BUG-008: Side effect in validation function (utils.py:112)

**Symptom:** `validate_excel_structure()` modifies input DataFrame.

**Root cause:** Line 112 renames column "PP" to "Privat" using `df.rename(..., inplace=True)`. Validation functions should be read-only.

**Risk:** Very low - Intentional behavior for data normalization, but violates SRP.

---

### BUG-009: Unused variable in usage_logger.py (line 194)

**Symptom:** `scheduled_time = time(7, 30)` is defined but never used.

**Root cause:** In `check_and_export_at_scheduled_time()`, the function name suggests time-based export, but it only checks for date changes, not time of day.

**Risk:** Very low - Dead code, function still works correctly for date changes.

---

### BUG-010: Unused BackgroundScheduler (app.py:41,54-55)

**Symptom:** A BackgroundScheduler is created, started, and registered for shutdown but has no scheduled jobs.

**Root cause:** The scheduler was likely added for future use or had jobs removed. Daily reset is handled via `before_request` hook instead.

**Risk:** Low - Wastes minimal resources (one background thread).

---

### BUG-011: Placeholder path in gunicorn_config.py (line 17) - FIXED

**Symptom:** Application will fail to start with gunicorn due to invalid log path.

**Root cause:** `logfile = "/xxxx/gunicorn.log"` is an obvious placeholder path that doesn't exist.

**Risk:** HIGH - Prevents production deployment with gunicorn.

**Fix applied:** Changed to use `logs/gunicorn.log` with directory creation.

---

## Code Quality Notes (Not Bugs)

1. **routes.py:** Many routes use `data = request.json` without null check. If client sends empty body, this returns `None` and subsequent `.get()` calls will fail. However, Flask's `request.json` returns `None` gracefully, and `.get()` on `None` raises `AttributeError`. This is a minor robustness issue.

2. **schedule_crud.py:** `_parse_gap_list()` catches all exceptions and returns empty list. This could mask parsing bugs but is acceptable for fault tolerance.

3. **state_manager.py:** Properties return direct references to internal dicts. This is intentional for performance but requires callers to acquire the lock for multi-step operations.

4. **JavaScript:** Good use of `escapeHtml()` for XSS prevention. Async error handling is properly implemented with try/catch.

5. **Templates:** Good use of Jinja's `tojson` filter for safe JSON embedding. Proper escaping throughout.

---

## Completion Summary

**All 8 phases reviewed.** Found 11 issues total:
- 1 HIGH severity (BUG-011) - FIXED
- 1 MEDIUM severity (BUG-001) - Documented
- 4 LOW severity - 1 FIXED, 3 Documented
- 5 VERY LOW severity - Documented

The codebase is generally well-structured with good practices:
- Proper locking patterns in most places
- XSS prevention with escapeHtml in JavaScript
- Safe JSON embedding in templates
- Defensive type coercion in config
