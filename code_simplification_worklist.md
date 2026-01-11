# Code Simplification Worklist

## Scope check
- [x] Identify starting scope: data_manager/file_ops.py
- [x] Expand scope: data_manager/*.py modules
- [x] Expand scope: lib/*.py utilities
- [x] Expand scope: routes.py, balancer.py
- [x] Expand scope: static/js/ JavaScript modules
- [x] Expand scope: templates/ front-end HTML templates
- [x] Expand scope: scripts/ and root-level Python files

## Behavior lock notes
- [x] data_manager/file_ops.py: backup, staged load, quarantine, initialization must preserve inputs/outputs and side effects (file IO, logging, state updates).
- [x] data_manager/csv_parser.py: CSV loading, shift/gap parsing, exclusions, and overlap resolution must preserve inputs/outputs and logging side effects.
- [x] lib/usage_logger.py: daily usage tracking, CSV export must preserve file format and threading behavior.
- [x] balancer.py: worker selection algorithm, weighting, and overflow logic must preserve exact selection behavior.
- [x] static/js/*.js: skill value normalization, timeline rendering, sorting, and filtering must preserve exact UI behavior.
- [x] templates/: HTML structure, CSS variables, and Jinja template logic must produce identical rendered output.
- [x] scripts/: CLI tools must preserve argument parsing, file I/O, and output formatting.
- [x] app.py, config.py, state_manager.py, gunicorn_config.py: preserve Flask init, scheduler setup, and config loading.

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
- [x] templates/: extracted shared admin header theme to partials/admin_theme.html, reducing duplication across skill_roster.html, prep_next_day.html, upload.html, worker_load_monitor.html.
- [x] scripts/ops_check.py: reviewed - clean, no changes needed.
- [x] scripts/exam_values.py: reviewed - well-structured, no changes needed.
- [x] scripts/code_aggregator.py: reviewed - clean class-based structure, no changes needed.
- [x] scripts/prepare_config.py: fixed duplicate keywords bug in keyword_map, simplified complex ternary for day_part lookup.
- [x] app.py: removed unused imports (modality_data, lock).
- [x] gunicorn_config.py: removed unused import (multiprocessing).
- [x] config.py, state_manager.py: reviewed - well-structured, no changes needed.

## Safety check
- [x] data_manager/file_ops.py changes verified for identical behavior.
- [x] data_manager module review completed for current scope.
- [x] lib/usage_logger.py: extracted shared CSV write helper, removed dead code.
- [x] balancer.py: removed unused imports (timedelta, Any, Tuple, WEIGHTED_SKILL_MARKER, save_state, get_local_now).
- [x] static/js/*.js: all changes preserve identical behavior; extracted helpers maintain same logic.
- [x] templates/: admin theme partial extraction verified; identical CSS output, only source refactored.
- [x] scripts/prepare_config.py: duplicate keyword removal preserves matching behavior; day_part logic unchanged.
- [x] app.py, gunicorn_config.py: unused import removal has no behavioral impact.

## Bugs discovered
- [x] scripts/prepare_config.py: Line 118 had duplicate keywords ["mammo", "mammo", "gyn", "gyn"] - fixed to ["mammo", "gyn"].

## Completion status
All scope items reviewed and completed. Full codebase simplification pass is now complete.
