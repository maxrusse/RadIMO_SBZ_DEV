# Feedback Work Items - RadIMO Cortex

## Overview

This document contains detailed work items derived from user feedback. Each item includes:
- Problem description
- Code context/location
- Implementation plan
- Priority estimate

---

## 1. DASHBOARD / ASSIGNMENT

### 1.1 ~~Latest Assignment → Show Previous Assignment~~ ✅ COMPLETED
**Feedback:** "latest assignment -> current assignment but should be the one before"

**Problem:** The footer shows "Letzte Zuweisung" (last assignment) but seems to show the CURRENT assignment, not the PREVIOUS one. User wants to see the assignment before the current one (history of n-1).

**Solution Implemented:**
- Added `currentAssignment` state variable to track assignment data
- Modified `showResult()` to display the previous assignment in footer
- Changed label from "Letzte Zuweisung" to "Vorherige Zuweisung" (Previous Assignment)
- Footer only appears after second assignment (when there's a previous to show)

**Priority:** Medium - UX improvement ✅ DONE

---

## 2. SKILL ROSTER

### 2.1 ~~Worker Names vs ID/Initials in Skill Roster~~ ✅ COMPLETED
**Feedback:** "Names of Worker vs ID / initials akronym-like entry -> in skillroaster -> load from csv -> no names ??"

**Problem:** Skill roster shows only IDs/initials, not full names. When loading from CSV, full names should be displayed.

**Solution Implemented:**
- Added `full_name` field to worker roster entries
- Modified `auto_populate_skill_roster()` to store full names from CSV
- Added `build_worker_name_mapping()` helper function to build display names
- Updated skill roster API to return `worker_names` mapping
- Updated `skill_roster.html` to display full names with ID tooltips
- Added support for "Name (ID)" format when manually adding workers

**Priority:** High - Data clarity improvement ✅ DONE

### 2.2 Default W-Weight for Skill = 0.5
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

### 2.3 Remove Optional/Special Flags from Config
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

### 3.2 ~~Names in Adding, Not Only Acronyms~~ ✅ COMPLETED
**Feedback:** "Names in adding not only akromyns"

**Problem:** When adding a worker, only acronyms/IDs are shown, not full names

**Solution Implemented:**
- Added `worker_names` mapping to `prep_next_day` route (using `build_worker_name_mapping`)
- Updated datalist in template to show "Full Name (ID)" format
- Added `parseWorkerInput()` JS function to extract worker ID from display format
- Added `getWorkerDisplayName()` JS helper for consistent name display
- Updated `onAddWorkerNameChange()` and `saveAddWorkerModal()` to use parsed worker IDs
- Worker skill roster lookups now work correctly with "Full Name (ID)" input

**Priority:** Medium - Usability improvement ✅ DONE

### 3.3 Separate Prep Today from Prep Tomorrow as Separate Pages
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

### 3.4 Popup Edit: Missing Shifts/Gaps
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

### 3.5 Add Worker = Use Edit Popup in Empty State
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

### 3.6 ~~Small X to Delete Shifts/Gaps in Quick Edit~~ ✅ COMPLETED
**Feedback:** "in quickedit maybe small x to delete shifts/gaps?"

**Problem:** Users had no way to delete shifts/gaps directly in quick edit mode

**Solution Implemented:**
- Added `.btn-inline-delete` CSS styling in `prep_next_day.html` for small red delete button
- Modified shift editor in quick edit mode to include × delete button after time inputs
- Added `deleteShiftInline(tab, gIdx, shiftIdx)` function in `prep_next_day.js`
- Delete button confirms before executing and removes all modality entries for the shift
- Uses existing `/api/prep-next-day/delete-worker` and `/api/live-schedule/delete-worker` endpoints

**Priority:** Medium - Usability improvement ✅ DONE

### 3.7 ~~Gaps Not Shown in Timetable~~ ✅ COMPLETED
**Feedback:** "gaps not shown in timetable?"

**Problem:** Timetable view doesn't display gap periods

**Solution Implemented:**
- Added `.gap-bar` CSS styling with diagonal stripe pattern and dashed border
- Modified `TimelineChart.render()` in `timeline.js` to render gap bars visually
- Gap bars appear on the timeline with a distinct gray striped pattern
- Added "Pause/Gap" legend item with matching styling
- Gap tooltips show worker name, activity type, and time range

**Priority:** Medium - Data visibility improvement ✅ DONE

### 3.8 ~~Filter Highlighting in Table~~ ✅ COMPLETED
**Feedback:** "on filter do a small Highlighting on the table like a bit thicker line around the selected stuff like CT + Gyn = edges around the entries a bit thicker?"

**Problem:** When filtering by modality/skill, the filtered items should have visual highlighting

**Solution Implemented:**
- Added `.filtered-highlight` CSS class in `prep_next_day.html` with outline and subtle background
- Modified `renderTable()` in `prep_next_day.js` to add the class when modality or skill filter is active
- Rows matching the filter now show a 2px blue outline and light blue background tint
- Worker group first rows have slightly thicker outline (2.5px) for better visibility

**Priority:** Low - Visual enhancement ✅ DONE

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

### 5.1 ~~Simplify Timetable Link to Always All~~ ✅ COMPLETED
**Feedback:** "simplify link to timetable always all http://../timetable?modality=all"

**Problem:** Timetable links should default to showing all modalities

**Solution Implemented:**
- Updated all timetable links in templates to use `modality='all'` parameter
- Modified files:
  - `templates/index.html` (2 links)
  - `templates/timetable.html` (2 links)
  - `templates/upload.html` (1 link)
  - `templates/index_by_skill.html` (2 links)
  - `templates/skill_roster.html` (1 link)
  - `templates/prep_next_day.html` (1 link)
  - `templates/worker_load_monitor.html` (1 link)

**Priority:** Low - Navigation simplification ✅ DONE

### 5.2 Multi-Shifts and Gaps in Timetable - One Row
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

### 6.1 ~~Header Color Not Good~~ ✅ COMPLETED
**Feedback:** "improve headers more -> worker load header color not good"

**Solution Implemented:**
- Changed table header background from light gray (`#f8f9fa`) to brand blue (`#004892`)
- Added white text color for better contrast
- Updated hover state to darker blue (`#003670`)
- Updated sortable indicators to be visible against blue background
- Updated card h3 titles to use brand blue color

**Priority:** Low - Visual polish ✅ DONE

### 6.2 ~~Table Color Like Prep Page~~ ✅ COMPLETED
**Feedback:** "worker load -> color of table like prep page"

**Solution Implemented:**
- Reduced font size from `0.85rem` to `0.78rem` (matching prep page)
- Reduced cell padding from `0.5rem 0.75rem` to `0.35rem 0.5rem`
- Added alternating row colors (`#fafafa` on even rows)
- Updated hover states to use brand blue tint (`rgba(0, 72, 146, 0.05)`)
- Added `vertical-align: middle` and `white-space: nowrap` for cleaner display
- Updated compact-grid sub-headers with brand blue color scheme (`#e8f0f7` bg, `#004892` text)

**Priority:** Low - Visual consistency ✅ DONE

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
1. 3.4 - Popup edit missing shifts/gaps
2. 4.1 - Load next day verification
3. ~~2.1 - Worker names vs IDs in roster~~ ✅

### Medium Priority (UX Improvements)
1. ~~1.1 - Latest assignment display~~ ✅
2. ~~3.2 - Names in add worker~~ ✅
3. 3.3 - Separate Today/Tomorrow pages
4. 3.5 - Add worker uses edit popup
5. ~~3.6 - Delete button in quick edit~~ ✅
6. ~~3.7 - Gaps in timetable~~ ✅
7. 5.2 - Multi-shifts in timetable

### Low Priority (Polish & Cleanup)
1. 2.2 - Default w-weight
2. 2.3 - Remove optional/special flags
3. ~~3.8 - Filter highlighting~~ ✅
4. 4.2 - Remove preload button
5. ~~5.1 - Simplify timetable link~~ ✅
6. ~~6.1 - Header color~~ ✅
7. ~~6.2 - Table color consistency~~ ✅
8. 7.1 - Rename Abdomen

---

## Next Steps

1. Review this document with stakeholder
2. Clarify any unclear items
3. Create implementation tickets for high priority items
4. Begin implementation in priority order
