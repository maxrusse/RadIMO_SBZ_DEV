# Feedback Work Items - RadIMO Cortex

## Overview

This document contains detailed work items derived from user feedback. Each item includes:
- Problem description
- Code context/location
- Implementation plan
- Priority estimate

---

## 1. DASHBOARD / ASSIGNMENT

No pending items in this category.

---

## 2. SKILL ROSTER

### 2.1 Default W-Weight for Skill = 0.5
**Feedback:** "defaults w-weight in skill = 0.5 for w"

**Problem:** When a skill value is set to 'w' (weighted), the default weight should be 0.5

**Code Location:**
- `templates/skill_roster.html:594-603` - New worker creation sets `modifier: 1.0`
- `balancer.py:107-114` - Weight calculation
- `config.yaml:291-294` - Quick break settings mention modifiers

**Current Behavior:**
```javascript
// skill_roster.html:594
rosterData[workerId] = { modifier: 1.0 };  // Default is 1.0
```

**Implementation Plan:**
1. Add configuration option for default w-weight:
   ```yaml
   balancer:
     default_w_modifier: 0.5
   ```
2. Update skill roster UI to default new 'w' values to 0.5
3. Update balancer to use configured default

**Priority:** Low - Configuration refinement

### 2.2 Remove Optional/Special Flags from Config
**Feedback:** "do we really still need these entries? optional: If true, skill can be toggled on/off by workers; special: If true, skill requires special handling"

**Problem:** `optional` and `special` flags in skill config may no longer be used.

**Code Location:**
- `config.yaml:88-93` - Skills have `optional` and `special` flags
- `config.py` - May reference these flags
- `balancer.py:354-516` - Might use `special` flag

**Current Behavior:**
```yaml
skills:
  Notfall:
    optional: false   # These may not be used
    special: false
```

**Implementation Plan:**
1. Search codebase for usages of `optional` and `special`
2. If not used in logic:
   - Remove from config.yaml
   - Remove from config.py loading
   - Update documentation
3. If used, document the actual behavior

**Priority:** Low - Technical debt cleanup

---

## 3. PREP PAGE / SCHEDULE EDIT

### 3.1 Large Edit Needed - Gaps Display Issue
**Feedback:** "Large edit needed for pre page and edit/gaps"

**This is a meta-issue encompassing several sub-issues below**

### 3.2 Separate Prep Today from Prep Tomorrow as Separate Pages
**Feedback:** "Seperate Prep today from pre tomorrow as separate Tags on high level like own page as upload page"

**Problem:** User wants separate pages/tabs for Today vs Tomorrow prep, similar to Upload page structure

**Code Location:**
- `templates/prep_next_day.html` - Single page with tabs
- `routes.py:793-1077` - API endpoints for prep

**Current Behavior:**
- Single page with `today` and `tomorrow` tabs
- Lazy loading of tab content

**Implementation Plan:**
Option A: Keep current tabs but improve visual separation
Option B: Create separate routes/pages:
1. `/prep-today` - Live schedule editing
2. `/prep-tomorrow` - Staging for tomorrow
3. Update navigation to show both as top-level links

**Priority:** Medium - UX restructuring (needs user clarification)

### 3.3 Popup Edit: Missing Shifts/Gaps
**Feedback:** "Popup edit: added gaps also shifts? missing in popup edit mode should be all shifts/gaps in there? (from csv 2 shifts are working!)? - no shift/gap removal possible at the moment?"

**Problem:**
1. Popup edit modal doesn't show all shifts/gaps
2. Cannot remove shifts/gaps from popup
3. Multiple shifts from CSV work but aren't editable

**Code Location:**
- `static/js/prep_next_day.js` - Modal rendering (needs search for `showEditModal` or similar)
- `static/js/prep_next_day.js:839-999` - `buildEntriesByWorker()` groups data

**Current Behavior:**
- Edit modal shows single entry
- No delete button for individual shifts/gaps within a worker's schedule

**Implementation Plan:**
1. Extend edit modal to show ALL shifts for a worker
2. Add per-shift delete button (small X)
3. Add ability to edit individual time segments
4. Implement `/api/prep-next-day/delete-shift` endpoint

**Priority:** High - Core functionality gap

### 3.4 Add Worker = Use Edit Popup in Empty State
**Feedback:** "Add Worker = use edit popup in 'empty' state?"

**Problem:** User wants "Add Worker" to use the same popup as "Edit Worker" but in empty/new mode

**Code Location:**
- `static/js/prep_next_day.js` - `openAddWorkerModal()` function
- `templates/prep_next_day.html:1367-1376` - Add worker modal

**Implementation Plan:**
1. Refactor to use single modal for both Add and Edit
2. Pass mode flag: `openWorkerModal('add')` vs `openWorkerModal('edit', rowData)`
3. Pre-populate fields when editing, leave blank when adding

**Priority:** Medium - UI consolidation

---

## 4. UPLOAD / CSV LOADING

### 4.1 Load Next Day - No Overwrite from Shifts over Roster
**Feedback:** "load next day -> no overwrite from shifts over roaster? -> really do it just like csv workflow on loading today? check it again"

**Problem:** Loading next day may not properly respect roster settings vs CSV shift data

**Code Location:**
- `data_manager/schedule_crud.py` - Schedule loading logic
- `data_manager/csv_parser.py` - CSV parsing
- `routes.py:530-792` - Upload and load endpoints

**Implementation Plan:**
1. Review and document current loading behavior
2. Ensure CSV data merges correctly with roster skills
3. Add option/flag for "overwrite roster" vs "merge with roster"
4. Test loading workflow for both today and tomorrow

**Priority:** High - Core functionality verification

### 4.2 Remove Preload Tomorrow from Upload Page
**Feedback:** "remove preload tomorrow? from upload page as it is lasy loaded anyways"

**Problem:** "Preload Tomorrow" button on upload page may be redundant since data is lazy-loaded

**Code Location:**
- `templates/upload.html:338-346` - Preload button
- `routes.py` - `/preload-from-master` endpoint
- `data_manager/scheduled_tasks.py` - Auto-preload logic

**Current Behavior:**
- Manual preload button exists
- Auto-preload happens at configured time
- Prep page lazy-loads data

**Implementation Plan:**
1. Evaluate if manual preload is ever needed
2. If not, remove button from upload.html
3. Keep API endpoint for programmatic/scheduled use
4. Alternatively, show button only when auto-preload hasn't run

**Priority:** Low - UI simplification

---

## 5. TIMETABLE

### 5.1 Multi-Shifts and Gaps in Timetable - One Row
**Feedback:** "Multishifts and gaps in timetable -> always one row (might have min overlaps -- Shift ending 15:00 next starting from 15:00) Filter timetable multi list scaling?"

**Problem:**
1. Workers with multiple shifts should be on one row
2. Handle edge cases like shifts ending/starting at same time
3. Filter scaling issues with multi-shift workers

**Code Location:**
- `static/js/timetable.js` - Timeline rendering
- `static/js/timeline.js` - Shared timeline module

**Implementation Plan:**
1. Group all shifts by worker into single row
2. Handle overlapping/adjacent shifts (15:00-15:00 boundary)
3. Stack multiple shift bars vertically within single row height
4. Adjust row height dynamically for workers with many shifts
5. Test filter behavior with multi-shift workers

**Priority:** Medium - Data visualization improvement

---

## 6. WORKER LOAD MONITOR

No pending items in this category.

---

## 7. CONFIG / SKILLS

### 7.1 Rename Abdomen to Abd/Onco
**Feedback:** "Abdomen -> Abd/Onco rename -> also in config and example v2"

**Code Location:**
- `config.yaml:143-151` - Abdomen skill definition
- `test_data/test_generated.yaml` - Test data references
- All templates showing skill labels

**Current Config:**
```yaml
Abdomen:
  label: Abdomen
  slug: abdomen
```

**Implementation Plan:**
1. Update `config.yaml`:
   ```yaml
   Abdomen:
     label: Abd/Onco  # Changed label
     slug: abdomen    # Keep slug for URL compatibility
   ```
2. Update test data files
3. Run tests to verify no breakage
4. Consider if slug should also change (may break existing data)

**Priority:** Low - Label change

---

## 8. UNCLEAR / NEEDS CLARIFICATION

### 8.1 W-Weight Default Value
The feedback mentions "defauls w-weight in skill = 0.5 for w" - need to clarify if this means:
- Default modifier when skill=w (currently 1.0, should be 0.5?)
- Or default skill value for new workers (currently 0)?

**Action:** Ask user for clarification

---

## Implementation Priority Summary

### High Priority (Core Functionality)
1. 3.3 - Popup edit missing shifts/gaps
2. 4.1 - Load next day verification

### Medium Priority (UX Improvements)
1. 3.2 - Separate Today/Tomorrow pages
2. 3.4 - Add worker uses edit popup
3. 5.1 - Multi-shifts in timetable

### Low Priority (Polish & Cleanup)
1. 2.1 - Default w-weight
2. 2.2 - Remove optional/special flags
3. 4.2 - Remove preload button
4. 7.1 - Rename Abdomen

---

## Next Steps

1. Review this document with stakeholder
2. Clarify any unclear items
3. Create implementation tickets for high priority items
4. Begin implementation in priority order
