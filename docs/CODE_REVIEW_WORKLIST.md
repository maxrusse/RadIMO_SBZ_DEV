# RadIMO Cortex Code Review Worklist (Content-Driven)

## Goal
Build a content-driven project analysis that maps the major paths and functions of the tool. This worklist is the foundation for targeted code checks and bug discovery. Security assessment is intentionally out of scope.

---

## 1) Map the Tool’s Major User Paths
Document each end-to-end path with inputs, outputs, and the code files involved.

1. **CSV Upload & Data Load**
   - User action: upload CSV(s)
   - Expected output: stored shifts/roster data visible in UI
   - Locate: upload routes, CSV parsing, data_manager ingestion
   - Capture edge cases: missing columns, invalid dates, duplicate rows

2. **Dashboard / Assignment Flow**
   - User action: view assignments, edit gaps/shifts, save changes
   - Expected output: updated assignments and state
   - Locate: dashboard routes, assignment logic, state_manager updates
   - Capture edge cases: missing worker, partial assignment, undo/redo

3. **Prep Pages (Today/Tomorrow)**
   - User action: open prep view, adjust roster/schedule
   - Expected output: correct day’s schedule and counts
   - Locate: prep routes, schedule calculations, template rendering
   - Capture edge cases: date rollover, timezone assumptions

4. **Skill Roster & Config**
   - User action: edit skills/config values
   - Expected output: updated skill roster or config-driven behavior
   - Locate: config handlers, roster logic, UI templates
   - Capture edge cases: invalid skill names, missing defaults

5. **Timetable / Worker Load Monitor**
   - User action: inspect timeline/load views
   - Expected output: accurate timeline + load calculations
   - Locate: timetable routes, load calculations, templates/static
   - Capture edge cases: overlapping shifts, empty roster

Deliverable: a short path summary for each flow listing the exact files and functions touched.

---

## 2) Identify Core Modules and Responsibilities
Create a concise map of the core modules and what they own.

- `app.py`: application entrypoint and setup
- `routes.py`: HTTP routes and request handling
- `state_manager.py`: in-memory state and mutations
- `data_manager/`: data loading, parsing, and transformations
- `balancer.py`: assignment/optimization logic
- `templates/`, `static/`: UI rendering and assets
- `config.py`, `config.yaml`: configuration and defaults

Deliverable: a module inventory with ownership notes and any overlaps.

---

## 3) Trace Critical Data Structures
Document the key in-memory structures and how they move through the system.

- Shift records (from CSV → parsed structures → state)
- Worker roster entries (skills, availability)
- Schedule/assignment outputs (per day, per worker)

Deliverable: data structure notes with file references where created/updated/consumed.

---

## 4) Spot Legacy or Unused Code While Mapping
As you map, flag anything that appears unused or outdated.

- Routes not linked from any UI path
- Templates not referenced by routes
- Config values never read
- Functions/modules with no call sites

Deliverable: a list of candidates to verify for removal.

---

## 5) Translate Findings into Code-Check Targets
Use the mapping to propose specific code-check areas.

- Validation checks (inputs, CSV columns, required fields)
- State consistency checks (mutations, rollback, determinism)
- Date/time handling checks (rollovers, day boundaries)
- Calculation checks (load/timeline/assignment math)

Deliverable: a short checklist of targeted code checks based on the mapped paths.

---

## Out of Scope
- Security assessment
- Performance benchmarking (unless a bug is found during mapping)
