# Special Tasks TODO

## Goals

## Config Structure (Draft)
- Create a dedicated `special_tasks` block in `config.yaml`.
- Each entry should include:
  - `name` (unique, slug-friendly ID)
  - `label` (button text)
  - `base_skill` (staffing + work-balance identity skill_mod combos)
  - `modalities_dashboards` (explicit list of modality dashboards to render on)
  - `skill_dashboards` (explicit list of skill dashboards to render on)
  - `work_amount` (value applied to work balance)
  - `allow_overflow` (explicit overflow control)
  - `display_order` (explicit ordering 999; default last)

## Data/Logic Areas to Review
- **Config parsing:** ensure special tasks are validated and normalized.
- **Dashboard rendering:** modality + skill pages should pull special tasks from config, no inference rules.
- **Assignment routing:** special task click should map to `base_skill` for staffing checks.
- **Work balance:** `work_amount` should apply only to special-task assignments.
- **Roster + skill_modality checks:** verify special tasks do not bypass skill/modality restrictions.
- **Analytics/usage logging:** ensure special task assignments are attributed to `base_skill`.

## UI/UX Tasks
- Confirm placement on modality dashboards (after skills by default).
- Confirm label rendering in the assignment result + footer.

## Compatibility
- Document the recommended defaults in `config.yaml`.

## Testing Checklist
- Start server, load modality dashboard, verify special tasks appear as configured.
