# RadIMO Cortex - Code Audit & Cleanup Plan

**Date:** 2025-12-14
**Scope:** app.py routes/APIs and templates

---

## Executive Summary

After auditing `app.py` (4409 lines) and all 7 templates, I identified:
- **6 legacy/unused routes** that can be removed
- **1 duplicate route** with the same functionality
- **3 missing template links** to existing features
- **0 issues with config.yaml** (all config entries are used)

---

## 1. UNUSED/LEGACY ROUTES (Can Be Removed)

### 1.1 `/edit` (POST) - `app.py:3959-4054`
**Status:** UNUSED - Legacy form-based route
**Replaced by:** `/api/live-schedule/update-row` and `/api/live-schedule/add-worker`
**Evidence:** No template references `url_for('edit')` or `/edit`
**Action:** DELETE route and function `edit_entry()`

### 1.2 `/delete` (POST) - `app.py:4057-4073`
**Status:** UNUSED - Legacy form-based route
**Replaced by:** `/api/live-schedule/delete-worker` and `/api/prep-next-day/delete-worker`
**Evidence:** No template references this route
**Action:** DELETE route and function `delete_entry()`

### 1.3 `/get_entry` (GET) - `app.py:4077-4110`
**Status:** UNUSED - Legacy helper for `/edit`
**Replaced by:** `/api/live-schedule/data` and `/api/prep-next-day/data`
**Evidence:** No template references this route
**Action:** DELETE route and function `get_entry()`

### 1.4 `/edit_info` (POST) - `app.py:3930-3943`
**Status:** UNUSED - Edits info_texts
**Evidence:** No template has a form posting to this route
**Note:** Info texts editing may be needed in future
**Action:** OPTIONAL - Mark as deprecated or keep for future use

### 1.5 `/preload-next-day` (POST) - `app.py:3104-3140`
**Status:** UNUSED - Requires file upload for preload
**Replaced by:** `/preload-from-master` (uses existing master CSV)
**Evidence:** Templates use `/preload-from-master` exclusively
**Action:** DELETE route and function `preload_next_day()`

### 1.6 `/download_latest` (GET) - `app.py:3945-3957`
**Status:** UNUSED - Downloads last uploaded file
**Evidence:** No template links to this route
**Action:** OPTIONAL - Remove or add link to upload.html

---

## 2. POTENTIALLY UNUSED API (Review Required)

### 2.1 `/api/prep-next-day/activate` (POST) - `app.py:3498-3553`
**Status:** DOCUMENTED but NOT USED
**Purpose:** Activates staged schedule by copying to live
**Evidence:** No template JavaScript calls this endpoint
**Note:** This may be intentional (activation happens via auto-preload at 7:30 AM)
**Action:** REVIEW - Confirm if manual activation is needed or remove

### 2.2 `/force-refresh-today` (POST) - `app.py:3266-3338`
**Status:** DOCUMENTED but NOT LINKED
**Purpose:** Complete rebuild with counter reset
**Evidence:** Not linked in upload.html UI
**Action:** OPTIONAL - Add button to upload.html or remove if not needed

---

## 3. MISSING TEMPLATE LINKS

### 3.1 upload.html - Missing Download Links
**File:** `templates/upload.html`
**Missing:** Links to `/download` and `/download_latest` routes
**Action:** Either remove the routes or add download buttons to the template

### 3.2 upload.html - Missing Force Refresh Button
**File:** `templates/upload.html`
**Missing:** Button for `/force-refresh-today`
**Action:** Add button if feature is needed, otherwise document in API.md only

---

## 4. CODE DUPLICATION

### 4.1 Legacy `/edit` route duplicates helper logic
**Location:** `app.py:3959-4054`
**Issue:** The `edit_entry()` function contains inline logic that duplicates:
- `_update_schedule_row()`
- `_add_worker_to_schedule()`

The new API routes properly use these shared helpers.
**Action:** DELETE the entire `/edit` route (covered by #1.1)

---

## 5. CONFIG.YAML - No Issues Found

All configuration entries in `config.yaml` are actively used:
- `modalities` - Used in templates and app.py
- `modality_fallbacks` - Used in app.py:441 for cross-modality overflow
- `skills` - Used throughout for skill definitions
- `skill_modality_overrides` - Used in weight calculations
- `skill_dashboard` - Used for UI behavior
- `balancer` - Used for load balancing logic
- `medweb_mapping` - Used for CSV parsing
- `shift_times` - Used in prep_next_day.html and app.py
- `worker_skill_roster` - Used for worker overrides

---

## 6. CLEANUP IMPLEMENTATION PLAN

### Phase 1: Remove Unused Routes (Safe)
```python
# DELETE these routes from app.py:

# 1. /edit route (lines 3959-4054)
# 2. /delete route (lines 4057-4073)
# 3. /get_entry route (lines 4077-4110)
# 4. /preload-next-day route (lines 3104-3140)
```

### Phase 2: Review and Decide
- `/edit_info` - Keep or remove?
- `/download_latest` - Add link to UI or remove?
- `/api/prep-next-day/activate` - Is manual activation needed?
- `/force-refresh-today` - Add UI button or remove?

### Phase 3: Update Documentation
- Update `docs/API.md` to remove references to deleted routes
- Mark deprecated routes if keeping them

---

## 7. LINES TO DELETE (Estimated)

| Route | Lines | Approx. LOC |
|-------|-------|-------------|
| `/edit` | 3959-4054 | ~95 |
| `/delete` | 4057-4073 | ~17 |
| `/get_entry` | 4077-4110 | ~34 |
| `/preload-next-day` | 3104-3140 | ~37 |
| **Total** | | **~183 lines** |

---

## 8. SUMMARY TABLE

| Item | Type | Status | Action |
|------|------|--------|--------|
| `/edit` | Route | UNUSED | DELETE |
| `/delete` | Route | UNUSED | DELETE |
| `/get_entry` | Route | UNUSED | DELETE |
| `/edit_info` | Route | UNUSED | REVIEW |
| `/preload-next-day` | Route | UNUSED | DELETE |
| `/download_latest` | Route | UNUSED | REVIEW |
| `/api/prep-next-day/activate` | API | UNUSED | REVIEW |
| `/force-refresh-today` | Route | NOT LINKED | REVIEW |
| config.yaml entries | Config | ALL USED | OK |
| Helper functions | Code | PROPERLY SHARED | OK |

---

## Next Steps

1. Confirm this cleanup plan with stakeholders
2. Create backup of app.py before changes
3. Delete unused routes in Phase 1
4. Decide on Phase 2 items
5. Update documentation
6. Test all remaining functionality
