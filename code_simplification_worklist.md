# Code Simplification Worklist

## Scope check
- [x] Identify starting scope: data_manager/file_ops.py
- [x] Expand scope: data_manager/*.py modules
- [ ] Expand scope: lib/*.py utilities
- [ ] Expand scope: app.py, routes.py, balancer.py
- [ ] Expand scope: static/ and templates/ front-end assets
- [ ] Expand scope: scripts/ and docs as needed

## Behavior lock notes
- [x] data_manager/file_ops.py: backup, staged load, quarantine, initialization must preserve inputs/outputs and side effects (file IO, logging, state updates).
- [x] data_manager/csv_parser.py: CSV loading, shift/gap parsing, exclusions, and overlap resolution must preserve inputs/outputs and logging side effects.

## Standards & clarity pass
- [x] data_manager/file_ops.py: apply PEP 8, type hints, explicit control flow.
- [x] data_manager/*.py: apply PEP 8, type hints, explicit control flow.
- [ ] lib/*.py: apply PEP 8, type hints, explicit control flow.
- [ ] app.py/routes.py/balancer.py: apply PEP 8, type hints, explicit control flow.
- [ ] static/templates: maintain layout, avoid inline styles.

## Safety check
- [x] data_manager/file_ops.py changes verified for identical behavior.
- [x] data_manager module review completed for current scope.
