# Feedback Work Items - RadIMO Cortex

## Overview

This document tracks detailed work items derived from user feedback. Each item includes:
- Problem description
- Code context/location
- Implementation plan
- Priority estimate

**Current Status:** All previous feedback items have been resolved. This document is ready for new feedback.

---

## 1. DASHBOARD / ASSIGNMENT

No pending items in this category.

---

## 2. SKILL ROSTER

No pending items in this category.

---

## 3. PREP PAGE / SCHEDULE EDIT

No pending items in this category.

---

## 4. UPLOAD / CSV LOADING

No pending items in this category.

---

## 5. TIMETABLE

No pending items in this category.

---

## 6. WORKER LOAD MONITOR

No pending items in this category.

---

## 7. CONFIG / SKILLS

No pending items in this category.

---

## Recently Resolved Items

All feedback items from the initial deployment phase have been successfully implemented:

### Core Functionality ✓
- Popup edit modal now shows all shifts/gaps with proper removal capability
- Load next day properly respects roster settings vs CSV shift data

### UX Improvements ✓
- Separated Today/Tomorrow prep pages with dedicated routes
- Consolidated add worker into edit modal with mode-aware actions
- Multi-shifts now display in single row with continuous timeline

### Polish & Cleanup ✓
- Added `balancer.default_w_modifier` (0.5) for weighted skill assignments
- Removed unused `optional` flag from config (kept `special` flag for styling)
- Removed "Preload Tomorrow" button from upload page
- Renamed skill label from "Abdomen" to "Abd/Onco"

---

## Next Steps

1. Monitor production usage for new feedback
2. Document new feature requests in this file
3. Continue iterating based on user needs
