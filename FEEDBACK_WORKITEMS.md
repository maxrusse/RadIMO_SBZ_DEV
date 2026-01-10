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

### 2.1 ~~Default W-Weight for Skill = 0.5~~ ✓ RESOLVED
**Feedback:** "defaults w-weight in skill = 0.5 for w"

**Resolution:**
- Added `balancer.default_w_modifier` (default `0.5`) in config defaults and `config.yaml`.
- Skill roster UI now uses the configured default for new workers and modifier display.
- Balancer uses the configured default when roster data omits a modifier.

### 2.2 ~~Remove Optional/Special Flags from Config~~ ✓ RESOLVED
**Feedback:** "do we really still need these entries? optional: If true, skill can be toggled on/off by workers; special: If true, skill requires special handling"

**Resolution:**
- **`optional` flag**: NOT USED anywhere in application logic. Removed from:
  - `config.yaml` - all skill definitions
  - `config.py` - loading code
  - `docs/CONFIGURATION.md` - documentation
- **`special` flag**: ACTIVELY USED in `templates/index.html:373` to add CSS class `special-btn` for distinct button styling (larger buttons for subspecialty skills). Kept in place.

---

## 3. PREP PAGE / SCHEDULE EDIT

### 3.1 Large Edit Needed - Gaps Display Issue
**Feedback:** "Large edit needed for pre page and edit/gaps"

**This is a meta-issue encompassing several sub-issues below**

### 3.2 ~~Separate Prep Today from Prep Tomorrow as Separate Pages~~ ✓ RESOLVED
**Feedback:** "Seperate Prep today from pre tomorrow as separate Tags on high level like own page as upload page"

**Resolution:**
- Added dedicated routes `/prep-today` and `/prep-tomorrow` with per-view titles and default tab selection.
- Updated navigation to expose both "Change Today" and "Prep Tomorrow" as top-level links with dedicated routes.

### 3.3 ~~Popup Edit: Missing Shifts/Gaps~~ ✓ RESOLVED
**Feedback:** "Popup edit: added gaps also shifts? missing in popup edit mode should be all shifts/gaps in there? (from csv 2 shifts are working!)? - no shift/gap removal possible at the moment?"

**Resolution:**
- Edit modal now renders from the unmerged shift list so each shift/gap entry is visible and editable.
- Modal actions (save/delete/presets) are aligned to that unmerged list so per-shift removal/editing works reliably.

### 3.4 ~~Add Worker = Use Edit Popup in Empty State~~ ✓ RESOLVED
**Feedback:** "Add Worker = use edit popup in 'empty' state?"

**Resolution:**
- Consolidated Add Worker into the existing edit modal with mode-aware actions and titles.
- Reused the add-worker content renderer to populate the edit modal in an empty state.

---

## 4. UPLOAD / CSV LOADING

### 4.1 ~~Load Next Day - No Overwrite from Shifts over Roster~~ ✓ RESOLVED
**Feedback:** "load next day -> no overwrite from shifts over roaster? -> really do it just like csv workflow on loading today? check it again"

**Problem:** Loading next day may not properly respect roster settings vs CSV shift data

**Resolution:**
- Scheduled JSON loads now reapply the current skill roster before staging or activating next-day data.
- Both daily reset loads and manual "Load Next Day" runs ensure roster exclusions/weighted rules override shift data.

**Priority:** High - Core functionality verification

### 4.2 ~~Remove Preload Tomorrow from Upload Page~~ ✓ RESOLVED
**Feedback:** "remove preload tomorrow? from upload page as it is lasy loaded anyways"

**Resolution:**
- Removed the "Preload Tomorrow" button and its client-side handler from `templates/upload.html`.
- Kept `/preload-from-master` endpoint and scheduled auto-preload behavior intact.

---

## 5. TIMETABLE

### 5.1 ~~Multi-Shifts and Gaps in Timetable - One Row~~ ✓ RESOLVED
**Feedback:** "Multishifts and gaps in timetable -> always one row (might have min overlaps -- Shift ending 15:00 next starting from 15:00) Filter timetable multi list scaling?"

**Resolution:**
- Timeline now keeps all of a worker’s shifts on a single row, merging overlapping/adjacent segments for a continuous bar while still showing discrete gaps.
- Adjacent (touching) shifts are treated as continuous so they render side by side without breaking the layout.

---

## 6. WORKER LOAD MONITOR

No pending items in this category.

---

## 7. CONFIG / SKILLS

### 7.1 ~~Rename Abdomen to Abd/Onco~~ ✓ RESOLVED
**Feedback:** "Abdomen -> Abd/Onco rename -> also in config and example v2"

**Resolution:**
- Updated the Abd/Onco skill label to `Abd/Onco` in:
  - `config.yaml`
  - `docs/CONFIGURATION.md`
  - `README.md`

**Current Config:**
```yaml
abd-onco:
  label: Abd/Onco
  slug: abd-onco
```

---

## Implementation Priority Summary

**STATUS: ALL ITEMS RESOLVED ✓**

All feedback work items have been successfully implemented and deployed:

### Core Functionality ✓
- ~~3.3 - Popup edit missing shifts/gaps~~ ✓ RESOLVED
- ~~4.1 - Load next day verification~~ ✓ RESOLVED

### UX Improvements ✓
- ~~3.2 - Separate Today/Tomorrow pages~~ ✓ RESOLVED
- ~~3.4 - Add worker uses edit popup~~ ✓ RESOLVED
- ~~5.1 - Multi-shifts in timetable~~ ✓ RESOLVED

### Polish & Cleanup ✓
- ~~2.1 - Default w-weight~~ ✓ RESOLVED
- ~~2.2 - Remove optional/special flags~~ ✓ RESOLVED
- ~~4.2 - Remove preload button~~ ✓ RESOLVED
- ~~7.1 - Rename Abd/Onco~~ ✓ RESOLVED

---

## Next Steps

1. Monitor production usage for any new feedback
2. Document any new feature requests in this file
3. Continue iterating based on user needs
