# Code Worklist

## Preload scheduling behavior
**Issue:** The next-workday preload runs on a fixed scheduler time (`auto_preload_time`). The desired behavior is to preload lazily on first use of the Prep Tomorrow page for the day.

**Suggested change:**
- Add a guard when serving `/prep-tomorrow` (or its data endpoint) to detect missing or stale staged data for the next workday and trigger `preload_next_workday` once per day.
- Persist the preload date in state to avoid re-running within the same day.

**Code locations:**
- `app.py` (scheduler wiring for `auto_preload_job`)
- `routes.py` (`auto_preload_job`, `/preload-from-master`, `/prep-tomorrow`, `/api/prep-next-day/data`)
- `data_manager/scheduled_tasks.py` (`preload_next_workday`)

## Live schedule refresh timing
**Observation:** Daily reset occurs on request via `before_request`, so the 07:30 refresh depends on traffic. A scheduled job might provide more predictable rollovers.

**Potential improvement:**
- Consider moving `check_and_perform_daily_reset` into a scheduled job (like auto-preload) or add a background cron to guarantee execution at `daily_reset_time`.

**Code locations:**
- `app.py` (`before_request` hook)
- `data_manager/scheduled_tasks.py` (`check_and_perform_daily_reset`)
