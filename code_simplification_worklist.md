# Code Simplification Worklist

## Scope check
- [x] Identify starting scope: data_manager/file_ops.py
- [x] Expand scope: data_manager/*.py modules
- [x] Expand scope: lib/*.py utilities
- [x] Expand scope: routes.py, balancer.py
- [x] Expand scope: static/js/ JavaScript modules
- [ ] Expand scope: templates/ front-end HTML templates
- [ ] Expand scope: scripts/ and docs as needed

## Behavior lock notes
- [x] data_manager/file_ops.py: backup, staged load, quarantine, initialization must preserve inputs/outputs and side effects (file IO, logging, state updates).
- [x] data_manager/csv_parser.py: CSV loading, shift/gap parsing, exclusions, and overlap resolution must preserve inputs/outputs and logging side effects.
- [x] lib/usage_logger.py: daily usage tracking, CSV export must preserve file format and threading behavior.
- [x] balancer.py: worker selection algorithm, weighting, and overflow logic must preserve exact selection behavior.
- [x] static/js/*.js: skill value normalization, timeline rendering, sorting, and filtering must preserve exact UI behavior.

## Standards & clarity pass
- [x] data_manager/file_ops.py: apply PEP 8, type hints, explicit control flow.
- [x] data_manager/*.py: apply PEP 8, type hints, explicit control flow.
- [x] lib/*.py: apply PEP 8, type hints, explicit control flow.
- [x] balancer.py: removed unused imports, added return type annotations.
- [x] routes.py: reviewed - well-structured, no changes needed.
- [x] static/js/prep_next_day.state.js: consolidated skill value functions using shared Set, switch for getSkillClass.
- [x] static/js/timeline.js: extracted parseTimeStr helper, simplified parseGapList early returns.
- [x] static/js/timetable.js: flattened isValidTimelineEntry guard clauses.
- [x] static/js/worker_load_monitor.js: extracted getSortValue helper, simplified sortWorkers.
- [ ] templates/: maintain layout, avoid inline styles.

## Safety check
- [x] data_manager/file_ops.py changes verified for identical behavior.
- [x] data_manager module review completed for current scope.
- [x] lib/usage_logger.py: extracted shared CSV write helper, removed dead code.
- [x] balancer.py: removed unused imports (timedelta, Any, Tuple, WEIGHTED_SKILL_MARKER, save_state, get_local_now).
- [x] static/js/*.js: all changes preserve identical behavior; extracted helpers maintain same logic.
