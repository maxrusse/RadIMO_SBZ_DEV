# Engineering Worklist

This document consolidates backlog items reported across multiple reviews. Items are grouped by priority, then category, and numbered for sequential execution.

## P1 — High

## P2 — Medium

### P2.1 — Live vs Staged Endpoint Duplication
- **File:** `routes.py`
- **Problem:** Endpoint pairs differ only by `use_staged` flag.
- **Impact:** Higher maintenance cost and risk of divergence.
- **Recommendation:** Create generic handler with `use_staged` parameter.

## P3 — Low

### P3.1 — TODO Placeholder Values in Config Generator
- **File:** `scripts/prepare_config.py:180,184,259`
- **Problem:** Placeholder `TODO_modality` requires manual cleanup.
- **Recommendation:** Ensure defaults are valid or enforce required inputs.

### P3.2 — Backwards Compatibility Re-exports
- **File:** `data_manager/__init__.py:15-27,159`
- **Problem:** Underscore-prefixed functions re-exported publicly.
- **Impact:** Legacy coupling and unclear ownership boundaries.

### P3.4 — Legacy Migration/Fallback Code
- **Files:** `data_manager/file_ops.py:590-612`, `data_manager/scheduled_tasks.py:116,185-187`
- **Problem:** Migration code for old file formats still present.
- **Recommendation:** Remove once migration is complete.
