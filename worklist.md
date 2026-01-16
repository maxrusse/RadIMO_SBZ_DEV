# Worklist

## Goals
- Use full-week “next day” logic (no weekend skip) and avoid holiday/working-day config for now.
- Keep auto-preload for the next day by default; use manual date selection to prep farther ahead (e.g., Friday → Monday).
- Drive prep UI from a server-provided target date instead of client-only date math.
- Allow admins to select and prep specific dates (including weekends) without breaking empty-shift handling.
- Ensure empty schedules (e.g., weekend with no staff) are handled safely (no crash when data is missing).
- Hide or disable “Break NOW” actions on the prep (tomorrow) tab.

## Change Plan
1. **Backend + UI alignment**
   - Update `lib/utils.get_next_workday()` to return the next calendar day (no weekend skip).
   - In `routes.py`, pass the server-calculated target date and weekday name into `/prep-tomorrow` template context.
   - Remove client-only date calculations in `static/js/prep_next_day.state.js` and use server values.

2. **Custom prep date selection (manual override)**
   - Add a date picker in `templates/prep_next_day.html` (prep tab header area) so admins can prep multiple days ahead.
   - Add a new backend route or extend existing preload/staged-data route to accept `target_date`.
   - Ensure staged metadata stores the target date to display in UI.
   - Confirm preload can safely handle empty schedules (e.g., Saturday/Sunday), returning success with zero workers.

3. **Disable “Break NOW” in prep tab**
   - Conditionally render quick break buttons only on the “today” tab in `static/js/prep_next_day.render.js`.
   - Add guard logic in `static/js/prep_next_day.actions.js` to block quick breaks when `currentTab === 'tomorrow'`.

## Acceptance Checklist
- Backend “next day” aligns with UI prep display (full-week logic).
- Admin can select a specific prep date and prep multiple days ahead.
- Empty weekend schedules do not crash and are stored with zero workers.
- “Break NOW” actions are unavailable on the prep tab.
