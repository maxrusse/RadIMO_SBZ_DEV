# Special Tasks Implementation Plan

Detailed step-by-step plan to add configurable special tasks to RadIMO Cortex.
Special tasks are manual buttons that map to skill x modality combos, appear on
explicit dashboards, and route to the underlying skill at assignment time.

---

## Design Decisions

### Config schema: `needed_skill_mod` combos

Instead of separate `base_skill` + `modalities` fields, each special task
declares **`needed_skill_mod`** — a list of `skill_modality` combo strings
(e.g. `gyn_mammo`, `uro_ct`). This single field defines:

1. Which **skill** is used for each modality at assignment time
   (parsed into a `mod_to_skill` mapping).
2. The default set of **modality dashboards** where the button appears
   (unique modalities extracted from the combos).
3. The default set of **skill dashboards** where the task appears
   (unique skills extracted from the combos).

### Dashboard visibility: inferred, overridable

- **`modalities_dashboard`** (optional list) — overrides the inferred modality
  dashboard list.  If omitted, derived from `needed_skill_mod`.
- **`skill_dashboards`** (optional list) — overrides the inferred skill
  dashboard list.  If omitted, derived from `needed_skill_mod`.
  Set to `[]` to hide from all skill dashboards.

### Display order default: 999

`display_order` defaults to **999** so special tasks render after standard
skills unless explicitly ordered.  This default lives in the Python code
(`coerce_int(task.get('display_order', 999))`) and is documented in the
`config.yaml` comment block.

### Color inheritance

Button/text colors are inherited from the **first combo's skill** unless the
task explicitly sets `button_color` / `text_color`.

---

## Files to Change (6 files)

### 1. `config.yaml` — add special_tasks section

**Location:** after the `skills:` block, before `skill_modality_overrides:`.

Add a comment header and the `special_tasks:` list.  Each entry has:

```yaml
# =============================================================================
# SPECIAL TASKS
# =============================================================================
# Special tasks are manual buttons that map to skill x modality combos.
# They appear on explicit dashboards and route to the underlying skill at
# assignment time.
#
# Fields:
#   name:                 Unique identifier (internal mapping key)
#   label:                Button label shown in UI
#   needed_skill_mod:     List of skill_modality combos (e.g., gyn_mammo, uro_ct).
#                         Defines which skill is used for each modality at
#                         assignment time.
#   modalities_dashboard: (optional) Modality dashboards where the button appears.
#                         Defaults to unique modalities from needed_skill_mod.
#   skill_dashboards:     (optional) Skill dashboards where the task appears.
#                         Defaults to unique skills from needed_skill_mod.
#   work_amount:          Workload multiplier (1.0 = same as base skill, default 1.0)
#   allow_overflow:       Allow overflow to generalists (default false)
#   display_order:        Sort order (lower first, default 999 - keeps special tasks
#                         after standard skills unless explicitly ordered)
# =============================================================================

special_tasks:
  - name: gyn_mammo_sono
    label: Gyn Mammo Sono
    needed_skill_mod:
      - gyn_mammo
    skill_dashboards: []           # don't show on skill dashboards
    work_amount: 1.0
    allow_overflow: false
    display_order: 0
  - name: uro_seg
    label: Uro Seg
    needed_skill_mod:
      - uro_ct
      - uro_mr
      - uro_xray
      - uro_mammo
    skill_dashboards: [uro]
    work_amount: 1.0
    allow_overflow: false
    display_order: 1
  - name: abd-onco_seg
    label: Abd/Onco Seg
    needed_skill_mod:
      - abd-onco_ct
      - abd-onco_mr
      - abd-onco_xray
    skill_dashboards: [abd-onco]
    work_amount: 1.0
    allow_overflow: false
    display_order: 2
```

---

### 2. `config.py` — parsing, globals, and lookup helpers

#### 2a. Inside `_build_app_config()`, after `config['skills'] = merged_skills`

Add a `# Special Tasks` block that:

1. **Builds local lookup dicts** (global maps don't exist yet at this point):
   ```python
   _skills_lower = {k.lower(): k for k in merged_skills}
   _slug_to_skill = {}  # slug.lower() -> canonical skill name
   for _sk, _sv in merged_skills.items():
       _sl = (_sv.get('slug') or '').lower()
       if _sl:
           _slug_to_skill[_sl] = _sk
   _mods_lower = {k.lower(): k for k in merged_modalities}
   ```

2. **Defines a local `_resolve_combo(combo_str)` helper** that splits on `_`
   (first occurrence only — handles hyphenated skill names like `abd-onco`),
   tries `skill_mod` ordering first, then `mod_skill`:
   ```python
   def _resolve_combo(combo_str: str):
       parts = combo_str.strip().lower().split('_', 1)
       if len(parts) != 2:
           return None
       a, b = parts
       skill = _skills_lower.get(a) or _slug_to_skill.get(a)
       mod = _mods_lower.get(b)
       if skill and mod:
           return (skill, mod)
       skill = _skills_lower.get(b) or _slug_to_skill.get(b)
       mod = _mods_lower.get(a)
       if skill and mod:
           return (skill, mod)
       return None
   ```

3. **Iterates `raw_config.get('special_tasks')`**, for each task dict:
   - Validate `name` is non-empty
   - Parse `needed_skill_mod` list through `_resolve_combo()` to build:
     - `skill_mod_combos`: list of `(skill, modality)` tuples
     - `mod_to_skill`: dict `{modality: skill}` for assignment-time lookup
   - Skip task if no combos resolve (log warning)
   - Generate `slug` via `_slugify(name)` if not explicit
   - **Infer dashboard lists** from combos (order-preserving unique):
     - `inferred_mod_dashboards` = unique modalities from combos
     - `inferred_skill_dashboards` = unique skills from combos
   - **Override if explicit** `modalities_dashboard` / `skill_dashboards`
     lists are present in config (validate each entry exists in
     `merged_modalities` / `merged_skills`)
   - Inherit `button_color` / `text_color` from first combo's skill config
   - Append the parsed dict with all fields:
     ```python
     {
         'name', 'label', 'slug',
         'skill_mod_combos',      # [(skill, mod), ...]
         'mod_to_skill',          # {mod: skill}
         'modalities_dashboard',  # [mod, ...]
         'skill_dashboards',      # [skill, ...]
         'work_amount',           # float, default 1.0
         'allow_overflow',        # bool, default False
         'display_order',         # int, default 999
         'button_color', 'text_color',
         'special',               # bool, default True
     }
     ```
   - Store as `config['special_tasks'] = special_tasks`

#### 2b. Global objects (after `APP_CONFIG = _build_app_config()`)

Add alongside existing globals:
```python
SPECIAL_TASKS = APP_CONFIG.get('special_tasks', [])
```

#### 2c. Lookup maps (after `ROLE_MAP` / `skill_columns_map`)

```python
SPECIAL_TASKS_BY_SLUG = {task['slug'].lower(): task for task in SPECIAL_TASKS}
SPECIAL_TASKS_BY_NAME = {task['name'].lower(): task for task in SPECIAL_TASKS}

def resolve_special_task(key: str) -> Optional[Dict[str, Any]]:
    """Resolve a special task by slug or name (case-insensitive)."""
    if not key:
        return None
    key_lower = key.lower().strip()
    return SPECIAL_TASKS_BY_SLUG.get(key_lower) or SPECIAL_TASKS_BY_NAME.get(key_lower)
```

Export `SPECIAL_TASKS` and `resolve_special_task` so `routes.py` can import them.

---

### 3. `balancer.py` — add `weight_multiplier` parameter

Change the signature of `update_global_assignment()`:

```python
def update_global_assignment(
    person: str,
    role: str,
    modality: str,
    is_weighted: bool = False,
    weight_multiplier: float = 1.0,    # <-- new
) -> str:
```

Update the docstring to document `weight_multiplier`.

In the weight calculation line, multiply by the new param:
```python
weight = get_skill_modality_weight(role, modality) * (1.0 / combined_modifier) * weight_multiplier
```

No other changes to balancer.py.

---

### 4. `routes.py` — routing, helpers, assignment flow

#### 4a. Imports

Add to the config import block:
```python
SPECIAL_TASKS,
resolve_special_task,
```

#### 4b. Helper functions (after `_validate_modality`)

Add three functions:

```python
def _get_special_tasks_for_modality(modality: str) -> list[dict]:
    """Return special tasks visible on a modality dashboard, sorted."""
    visible = []
    for task in SPECIAL_TASKS:
        if modality in task.get('modalities_dashboard', []):
            visible.append(task)
    return sorted(visible, key=lambda t: (t.get('display_order', 999), t.get('label', '')))


def _get_special_tasks_for_skill(skill: str, visible_modalities: list[str]) -> list[dict]:
    """Return special tasks for a skill dashboard with their allowed modalities."""
    visible = []
    for task in SPECIAL_TASKS:
        if skill not in task.get('skill_dashboards', []):
            continue
        allowed_mods = [
            mod for mod in visible_modalities
            if mod in task.get('modalities_dashboard', [])
        ]
        if not allowed_mods:
            continue
        task_copy = dict(task)
        task_copy['visible_modalities'] = allowed_mods
        visible.append(task_copy)
    return sorted(visible, key=lambda t: (t.get('display_order', 999), t.get('label', '')))


def _resolve_assignment_role(role: str, modality: str) -> tuple[str, Optional[dict]]:
    """Resolve role slug to effective skill, handling special tasks.

    Returns (effective_skill, special_task_or_None).
    """
    special_task = resolve_special_task(role)
    if special_task:
        mod_to_skill = special_task.get('mod_to_skill', {})
        effective_skill = mod_to_skill.get(modality)
        if not effective_skill:
            # Fallback to first combo's skill (URL has unexpected modality)
            combos = special_task.get('skill_mod_combos', [])
            effective_skill = combos[0][0] if combos else normalize_skill(role)
            selection_logger.warning(
                "Special task '%s' has no combo for modality '%s', falling back to '%s'",
                special_task.get('name'), modality, effective_skill,
            )
        return effective_skill, special_task
    return normalize_skill(role), None
```

#### 4c. `index()` route

After computing `visible_skills`, add:
```python
visible_special_tasks = _get_special_tasks_for_modality(modality)
```

Pass `special_tasks=visible_special_tasks` to `render_template('index.html', ...)`.

#### 4d. `index_by_skill()` route

After computing `visible_modalities`, add:
```python
special_tasks = _get_special_tasks_for_skill(skill, visible_modalities)
```

Pass `special_tasks=special_tasks` to `render_template('index_by_skill.html', ...)`.

#### 4e. `_assign_worker()` function

At the top of the try block, **before** the `is_no_overflow` check:
```python
effective_role, special_task = _resolve_assignment_role(role, modality)

if special_task and not special_task.get('allow_overflow', False):
    allow_overflow = False
```

Then change `normalize_skill(role)` to `normalize_skill(effective_role)` for
the `canonical_skill` / `is_no_overflow` check.

Pass `effective_role` (not `role`) to `get_next_available_worker()`:
```python
result = get_next_available_worker(
    now,
    role=effective_role,
    ...
)
```

When falling back for `actual_skill`:
```python
if not actual_skill:
    actual_skill = effective_role   # was: role
```

Add weight multiplier when calling `update_global_assignment`:
```python
weight_multiplier = 1.0
if special_task:
    weight_multiplier = special_task.get('work_amount', 1.0)
canonical_id = update_global_assignment(
    person,
    actual_skill,
    actual_modality,
    is_weighted,
    weight_multiplier=weight_multiplier,
)
```

---

### 5. `templates/index.html` — modality dashboard buttons

#### 5a. Button grid

After the `{% endfor %}` that closes the skill buttons loop, add a second loop
for special tasks:

```jinja2
{% for task in special_tasks %}
<div class="skill-button-wrapper" data-skill-slug="{{ task.slug }}" data-skill-name="{{ task.name }}">
  <button id="skill-btn-{{ task.slug }}" data-skill-name="{{ task.name }}"
    onclick="getNextAssignment('{{ task.slug }}', '{{ task.label }}')"
    class="btn assignment-btn skill-main-btn {% if task.special %}special-btn{% endif %}">
    {{ task.label }}
  </button>
  <button type="button" class="btn assignment-btn skill-strict-btn"
    onclick="getNextAssignment('{{ task.slug }}', '{{ task.label }}', true)"
    aria-label="Nur diese Gruppe (kein Fallback)" title="Nur diese Gruppe">
    *
  </button>
</div>
{% endfor %}
```

#### 5b. JavaScript: button coloring

In the `injectDynamicStyles` IIFE, merge special task definitions into the
button coloring loop:

```javascript
const specialTaskDefinitions = JSON.parse('{{ special_tasks|tojson|safe }}');
const buttonDefinitions = skillDefinitions.concat(specialTaskDefinitions);
```

Then change the `skillDefinitions.forEach(...)` loop to iterate over
`buttonDefinitions` instead, so special task buttons get `--btn-bg` /
`--btn-text` CSS vars set on their wrappers.

---

### 6. `templates/index_by_skill.html` — skill dashboard buttons

#### 6a. CSS additions

Add these styles (inside `{% block styles %}`):

```css
.special-task-section {
  margin-top: 1.5rem;
}
.special-task-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}
.special-task-label {
  font-size: 1rem;
  font-weight: 600;
  margin: 0.5rem 0;
}
```

#### 6b. HTML: special task section

After the main `</div>` closing `#buttonGrid`, add:

```jinja2
{% if special_tasks %}
<div class="special-task-section">
  <div class="special-task-title">Special Tasks</div>
  {% for task in special_tasks %}
  <div class="special-task-label">{{ task.label }}</div>
  <div class="button-grid">
    {% for mod_key in task.visible_modalities %}
    <div class="modality-button-wrapper" data-modality="{{ mod_key }}">
      <button id="mod-btn-{{ mod_key }}-{{ task.slug }}" data-modality="{{ mod_key }}"
        onclick="getNextAssignment('{{ mod_key }}', false, '{{ task.slug }}', '{{ task.label }}')"
        class="btn assignment-btn modality-main-btn">
        {{ modalities[mod_key].label }}
      </button>
      <button type="button" class="btn assignment-btn modality-strict-btn"
        onclick="getNextAssignment('{{ mod_key }}', true, '{{ task.slug }}', '{{ task.label }}')"
        aria-label="Nur diese Modalitat (kein Fallback)" title="Nur diese Modalitat">
        *
      </button>
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</div>
{% endif %}
```

#### 6c. JavaScript: `getNextAssignment` and `showResult`

Update `getNextAssignment` to accept two new optional params:

```javascript
function getNextAssignment(modality, forcePrimary = false, roleOverride = null, labelOverride = null) {
    ...
    const targetRole = roleOverride || currentSkillSlug;
    const encodedSkill = encodeURIComponent(targetRole);
    ...
    // pass labelOverride through to showResult
    showResult(data.selected_person || '', modality, labelOverride);
}
```

Update `showResult` to accept and display `labelOverride`:

```javascript
function showResult(person, modality, labelOverride = null) {
    ...
    const contextLabel = labelOverride
        ? `${modalityLabel} \u00b7 ${labelOverride}`
        : modalityLabel;
    // Use contextLabel in the result panel
    // Use labelOverride || currentSkillLabel in the footer
    const footerLabel = labelOverride || currentSkillLabel;
    lastEl.textContent = `Letzte Zuweisung: ${timeStr} \u00b7 ${displayPerson} \u00b7 ${mod}/${footerLabel}`;
}
```

---

## API Paths (unchanged)

- `/api/<modality>/<role>` — normal assignment
- `/api/<modality>/<role>/strict` — strict (no overflow)

Special task slugs are passed as `<role>` and resolved back to their base
skill via `_resolve_assignment_role()`.  No new routes needed.

## Roster / Skill x Modality Logic (unchanged)

Worker roster and `skill_modality` combos still govern who can be selected.
Special tasks only map to a skill at assignment time — they don't change who
is eligible.  The `mod_to_skill` lookup picks the right skill for the
current modality from the combos.

---

## Verification Checklist

- [ ] `python -c "import ast; ast.parse(open('config.py').read())"` — no syntax errors
- [ ] `python -c "from config import SPECIAL_TASKS; print(len(SPECIAL_TASKS))"` — prints 3
- [ ] Each task has correct `skill_mod_combos`, `mod_to_skill`, dashboard lists
- [ ] `resolve_special_task('gyn-mammo-sono')` returns the gyn task (slug lookup)
- [ ] `resolve_special_task('uro_seg')` returns the uro task (name lookup)
- [ ] `resolve_special_task('nonexistent')` returns `None`
- [ ] Modality dashboard (e.g. mammo) shows Gyn Mammo Sono button
- [ ] Skill dashboard (e.g. uro) shows Uro Seg with CT/MR/Xray/Mammo buttons
- [ ] Clicking a special task button hits `/api/<mod>/<slug>` and gets a worker
- [ ] `work_amount` multiplier is applied to weighted count in balancer
- [ ] `allow_overflow: false` prevents fallback to generalists
