# Code Worklist

## Live schedule refresh timing
**Observation:** Daily reset occurs on request via `before_request`, so the 07:30 refresh depends on traffic. A scheduled job might provide more predictable rollovers.

**Potential improvement:**
- Consider moving `check_and_perform_daily_reset` into a scheduled job (like auto-preload) or add a background cron to guarantee execution at `daily_reset_time`.

**Code locations:**
- `app.py` (`before_request` hook)
- `data_manager/scheduled_tasks.py` (`check_and_perform_daily_reset`)
