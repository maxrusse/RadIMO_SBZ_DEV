# Alternative Weight Calculation -- Modality Code Multiplier

## Overview

New customer requires a simplified weight model where **all skill weights are 1** (flat), but a **4-digit code per modality** applies an additional multiplier. Codes are stored in a **separate `config_code.yaml`** file. The code is selected via a popup after a user clicks on a skill-modality combination (e.g. CT > abd-onco).

---

## What Changes

| Aspect | Current System | New Customer Model |
|---|---|---|
| Skill weights | Per-skill (e.g. notfall=1.1, card-thor=1.2) | **All skills = 1.0** |
| Modality factors | Per-modality (ct=1.0, mr=1.2, xray=0.33, mammo=0.5) | **Stays as-is** |
| Skill x Modality overrides | Explicit overrides (e.g. mr+card-thor=1.8) | **Removed / not used** |
| Worker modifiers (global, w) | Per-worker in roster (inverse: divide) | **Stays as-is** |
| Modality code multiplier | Does not exist | **NEW -- per-modality code list in `config_code.yaml`** |
| `config.yaml` | Full config | **Unchanged** (only add `weight_mode` flag) |
| Balancer logic | Unchanged | Unchanged (consumes final weight) |

**Existing `config.yaml` stays fully intact. One flag is added. All code data lives in `config_code.yaml`.**

---

## Weight Formula

### Full Chain (New Customer)

```
final_weight = skill_weight            = 1.0    (always 1, from config)
             * modality_factor         = 1.1    (from config.yaml, e.g. mr=1.2, ct=1.0)
             * code_value              = 2.1    (from config_code.yaml, e.g. CT code 0601)
             / w_modifier              / 0.5    (inverse -- trainee modifier, from roster)
             / global_modifier         / 1.2    (inverse -- per-worker global, from roster)
```

### Walkthrough Example

```
Scenario: MR assignment, code 0601 (value 2.1), trainee (w=0.5), worker global=1.2

  skill       = 1.0                         (flat, always 1)
  * modality  = 1.0 * 1.2       = 1.2       (MR factor from config.yaml)
  * code      = 1.2 * 2.1       = 2.52      (code 0601 has value 2.1 for MR)
  / w_mod     = 2.52 / 0.5      = 5.04      (trainee gets double effective weight)
  / global    = 5.04 / 1.2      = 4.2       (worker reduced capacity)
                                  ===
  final_weight = 4.2
```

### Comparison to Current Formula

```
CURRENT:   skill_weight * modality_factor / w_modifier / global_modifier
NEW:       1.0          * modality_factor * code_value / w_modifier / global_modifier
            ^-- forced 1                   ^-- NEW
```

Only two differences:
1. `skill_weight` is always **1.0** (no per-skill weighting).
2. `code_value` is a **new multiplier** from the selected 4-digit code.

### Modifier Direction Summary

| Factor | Direction | Example | Effect |
|---|---|---|---|
| `skill_weight` | multiply | 1.0 | always 1, no effect |
| `modality_factor` | multiply | 1.2 | MR counts 20% more |
| `code_value` | multiply | 2.1 | code makes it heavier |
| `w_modifier` | **divide** (inverse) | 0.5 | trainee: dividing by 0.5 = x2 effective weight |
| `global_modifier` | **divide** (inverse) | 1.2 | reduced capacity: dividing by 1.2 = less throughput |

---

## `config_code.yaml` -- Separate Code File

### Structure

Codes are grouped **per modality**. Each modality has its own list of ~100 codes. Codes **can overlap** between modalities (same code number, different multiplier).

```yaml
# config_code.yaml
# 4-digit modality codes with weight multipliers
# Organized per modality -- codes can appear in multiple modalities with different values

ct:
  "0601":
    label: "Abdomen Spezial"
    value: 2.1
  "0602":
    label: "Abdomen Standard"
    value: 1.0
  "0301":
    label: "Thorax Komplex"
    value: 1.8
  "0302":
    label: "Thorax Standard"
    value: 1.0
  "0701":
    label: "Neuro Komplex"
    value: 1.5
  # ... ~100 codes total for CT

mr:
  "0601":
    label: "Abdomen Spezial"
    value: 2.0          # same code, different value than CT
  "0602":
    label: "Abdomen Standard"
    value: 1.2
  "0701":
    label: "Neuro Komplex"
    value: 2.5           # MR neuro weighted higher than CT neuro
  # ... ~100 codes total for MR

xray:
  "1001":
    label: "Thorax ap/lat"
    value: 1.0
  "1002":
    label: "Abdomen leer"
    value: 1.0
  # ... ~100 codes total for X-ray

mammo:
  "2001":
    label: "Screening beidseits"
    value: 1.0
  "2002":
    label: "Diagnostisch"
    value: 1.5
  # ... ~100 codes total for Mammo
```

### Key Design Decisions

- **Per-modality grouping:** Codes are scoped to a modality. The popup only shows codes for the current modality.
- **Overlap allowed:** Code `0601` can exist in both CT and MR with different values.
- **Simple value:** Each code has one `value` (float multiplier), not a nested per-modality map.
- **Default:** If no code is selected, `code_value = 1.0`.

---

## UI Changes

### Popup (Code Selection)

- **Trigger:** User clicks a skill button on a modality page (e.g. CT > abd-onco).
- **Content:** Scrollable list of codes **for the current modality only** (from `config_code.yaml`).
- **Display format per row:** `0601 -- Abdomen Spezial (x2.1)`
- **Selection:** Clicking a code applies it and proceeds with the assignment.
- **Default:** If popup is dismissed without selection, use `code_value = 1.0`.
- **Search/filter:** With ~100 codes, a search/filter input at the top of the popup is useful.

### Where to Show the Active Code

- After selection, the code should be visible on the assignment card / worker row.
- Show: `0601 (x2.1)` next to the assignment.
- Optionally show the final computed weight.

---

## Config Changes

### `config.yaml` (minimal addition)

```yaml
# Add ONE flag to existing config.yaml -- everything else stays untouched
weight_mode: "modality_code"   # Options: "default" | "modality_code"
```

When `weight_mode: "modality_code"`:
- All skill weights from `skills:` section are ignored (treated as 1.0).
- `skill_modality_overrides:` are ignored.
- `config_code.yaml` is loaded and codes become available in the UI.
- Modality `factor:` values are still used.
- Worker modifiers (`global_modifier`, `modifier`) are still used.

When `weight_mode: "default"` (or not set):
- Everything works exactly as today. `config_code.yaml` is not loaded.

### New File: `config_code.yaml`

- Lives next to `config.yaml` in the project root.
- Loaded only when `weight_mode: "modality_code"`.
- Structure as shown above.

---

## Impact on Code

### `config.py`

```python
# Load code config when mode is active
def load_code_config():
    if config.get('weight_mode') == 'modality_code':
        with open('config_code.yaml') as f:
            return yaml.safe_load(f)
    return {}

code_config = load_code_config()

def get_code_value(modality: str, code: str) -> float:
    """Get multiplier for a 4-digit code within a modality."""
    return code_config.get(modality, {}).get(code, {}).get('value', 1.0)

def get_codes_for_modality(modality: str) -> dict:
    """Get all available codes for a modality (for popup)."""
    return code_config.get(modality, {})

def get_skill_modality_weight(skill: str, modality: str, code: str = None) -> float:
    if config.get('weight_mode') == 'modality_code':
        base = 1.0  # all skills = 1
        modality_factor = modality_factors.get(modality, 1.0)
        code_value = get_code_value(modality, code) if code else 1.0
        return base * modality_factor * code_value
    else:
        # existing default logic unchanged
        modality_overrides = skill_modality_overrides.get(modality, {})
        if skill in modality_overrides:
            return modality_overrides[skill]
        return skill_weights.get(skill, 1.0) * modality_factors.get(modality, 1.0)
```

### `balancer.py`

Existing formula already does `/ global_modifier` and `/ w_modifier`. The only change is passing the selected `code` into `get_skill_modality_weight()`:

```python
# In update_global_assignment():
weight = get_skill_modality_weight(role, modality, code=selected_code) * (1.0 / combined_modifier)
#                                                  ^-- NEW parameter
```

### `routes.py`

- Add API endpoint to serve codes for a modality: `GET /api/codes/<modality>`
- Accept `code` parameter when creating assignments.

### Templates / JS

- Add popup component triggered on skill-button click.
- Fetch codes from `/api/codes/<modality>`, render list with search.
- Pass selected code back with the assignment request.

---

## Implementation Steps

- [ ] Add `weight_mode: "modality_code"` flag to `config.yaml`
- [ ] Create `config_code.yaml` with placeholder/example codes per modality
- [ ] Add `load_code_config()`, `get_code_value()`, `get_codes_for_modality()` to `config.py`
- [ ] Modify `get_skill_modality_weight()` to support `modality_code` mode
- [ ] Add `/api/codes/<modality>` endpoint in `routes.py`
- [ ] Add popup UI component (template + JS) for code selection on skill-button click
- [ ] Pass selected code through assignment flow into `balancer.py`
- [ ] Store selected code on the assignment record for audit/display
- [ ] Display active code + weight on assignment cards and worker load monitor
- [ ] Add tests for new weight formula and code loading
- [ ] Get final code lists (~100 per modality) from customer and populate `config_code.yaml`

---

## Open Questions

1. **Complete code lists:** Customer needs to provide all 4-digit codes per modality with their multiplier values.
2. **Code filtering by skill:** Should certain codes only appear for certain skills, or are all codes available for every skill within a modality?
3. **Persistence:** Should the last-used code be remembered per skill-modality combo, or selected fresh each assignment?
4. **Reporting:** Does the customer need weight reports broken down by code?
5. **Code management UI:** Should there be an admin page to edit `config_code.yaml` codes, or is file editing sufficient?
6. **Fallback behavior:** If `config_code.yaml` is missing but `weight_mode` is set, should we error or fall back to default mode?
