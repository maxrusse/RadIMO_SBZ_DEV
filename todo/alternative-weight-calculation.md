# Alternative Weight Calculation -- Modality Code Multiplier

## Overview

New customer requires a simplified weight model where **all skill weights are 1** (flat), but a **modality-specific 4-digit numeric code** applies an additional multiplier. The code is selected via a popup after a user clicks on a skill-modality combination (e.g. CT > abd-onco).

---

## What Changes

| Aspect | Current System | New Customer Model |
|---|---|---|
| Skill weights | Per-skill (e.g. notfall=1.1, card-thor=1.2) | **All skills = 1.0** |
| Modality factors | Per-modality (ct=1.0, mr=1.2, xray=0.33, mammo=0.5) | Per-modality factor stays as-is |
| Skill x Modality overrides | Explicit overrides (e.g. mr+card-thor=1.8) | **Removed / not used** |
| Modality code multiplier | Does not exist | **NEW -- 4-digit code popup, multiplier per modality** |
| Worker modifiers (global, w) | Per-worker in roster | Stays the same |
| Balancer logic | Unchanged | Unchanged (consumes final weight) |

**Everything else (assignment logic, worker modifiers, UI flow) stays the same.**

---

## New Concept: Modality Code Multiplier

### How It Works

1. User navigates to a modality page (e.g. CT) and clicks a skill button (e.g. abd-onco).
2. **A popup appears** showing a list of 4-digit modality codes (e.g. `0601`).
3. The user selects a code. Each code carries a **per-modality weight multiplier**.
4. The selected code's multiplier is applied to the assignment weight.

### Weight Formula (New Customer)

```
final_weight = 1.0                          (skill weight, always 1)
             * modality_factor              (from config, e.g. ct=1.0, mr=1.2)
             * modality_code_multiplier     (from code lookup, e.g. 2.0)
             * (1 / combined_modifier)      (worker modifier, unchanged)
```

Compare to current formula:
```
final_weight = skill_weight * modality_factor * (1 / combined_modifier)
```

The only differences:
- `skill_weight` is hardcoded to **1.0** for all skills.
- A new `modality_code_multiplier` factor is introduced.

---

## Modality Code Lookup Table

Each 4-digit code defines a multiplier **per modality**. If a modality is not listed for a code, the multiplier defaults to **1** (no change).

### Example Structure

```yaml
modality_codes:
  "0601":
    label: "Abdomen CT/MR Spezial"
    multipliers:
      ct: 2.0
      mr: 2.0
      # xray: not listed -> defaults to 1.0
      # mammo: not listed -> defaults to 1.0

  "0701":
    label: "Neuro MR Komplex"
    multipliers:
      mr: 2.5
      # ct, xray, mammo -> 1.0

  "0301":
    label: "Thorax Standard"
    multipliers:
      ct: 1.5
      # rest -> 1.0

  "0100":
    label: "Standard (alle Modalitaeten)"
    multipliers: {}
    # all default to 1.0 -> effectively no multiplier
```

### Full Code List (TO BE FILLED IN)

| Code | Label | CT | MR | X-ray | Mammo |
|------|-------|----|----|-------|-------|
| `0601` | _TBD_ | 2.0 | 2.0 | 1.0 | 1.0 |
| `0701` | _TBD_ | 1.0 | 2.5 | 1.0 | 1.0 |
| `0301` | _TBD_ | 1.5 | 1.0 | 1.0 | 1.0 |
| `0100` | Standard | 1.0 | 1.0 | 1.0 | 1.0 |
| ... | ... | ... | ... | ... | ... |

> **Action required:** Customer must provide the complete list of 4-digit codes with their per-modality multipliers.

---

## UI Changes

### Popup (Code Selection)

- **Trigger:** User clicks a skill button on a modality page (e.g. CT > abd-onco).
- **Content:** List/dropdown of available 4-digit codes with their label and the multiplier value for the **current modality**.
- **Display format per row:** `0601 -- Abdomen CT/MR Spezial (x2.0)`
- **Selection:** Clicking a code applies it and proceeds with the assignment as usual.
- **Default:** If no code is selected (or popup is dismissed), use multiplier **1.0**.

### Where to Show the Active Code

- After selection, the code should be visible on the assignment card / worker row so it is clear which multiplier was applied.
- Optionally show the resulting weight next to it.

---

## Config Changes

### New Section in `config.yaml`

```yaml
# Alternative weight mode for customers using modality code multipliers
weight_mode: "modality_code"   # Options: "default" | "modality_code"

# When weight_mode = "modality_code", all skill weights are forced to 1.0
# and the following codes are available:
modality_codes:
  "0601":
    label: "Abdomen CT/MR Spezial"
    multipliers:
      ct: 2.0
      mr: 2.0
  "0701":
    label: "Neuro MR Komplex"
    multipliers:
      mr: 2.5
  "0301":
    label: "Thorax Standard"
    multipliers:
      ct: 1.5
  "0100":
    label: "Standard"
    multipliers: {}
```

### Impact on `config.py`

```python
def get_skill_modality_weight(skill: str, modality: str, code: str = None) -> float:
    if config.get('weight_mode') == 'modality_code':
        base = 1.0  # all skills = 1
        modality_factor = modality_factors.get(modality, 1.0)
        code_multiplier = 1.0
        if code:
            code_entry = modality_codes.get(code, {})
            code_multiplier = code_entry.get('multipliers', {}).get(modality, 1.0)
        return base * modality_factor * code_multiplier
    else:
        # existing default logic
        ...
```

---

## Implementation Steps

- [ ] Add `weight_mode` and `modality_codes` section to `config.yaml`
- [ ] Parse new config in `config.py`, expose `get_modality_code_multiplier(code, modality)`
- [ ] Modify `get_skill_modality_weight()` to support `modality_code` mode (all skills=1, apply code multiplier)
- [ ] Add popup UI component (template + JS) for code selection on skill-button click
- [ ] Pass selected code through assignment flow into `balancer.py`
- [ ] Store selected code on the assignment record for audit/display
- [ ] Display active code + resulting weight on worker load monitor
- [ ] Add tests for new weight formula
- [ ] Get final code list from customer and populate config

---

## Open Questions

1. **Complete code list:** Customer needs to provide all 4-digit codes with their per-modality multipliers.
2. **Code filtering by modality:** Should the popup only show codes that have a multiplier > 1 for the current modality, or always show all codes?
3. **Code filtering by skill:** Should certain codes only be available for certain skills, or are all codes available everywhere?
4. **Persistence:** Should the selected code be saved as a preference per skill-modality, or selected fresh each time?
5. **Reporting:** Does the customer need weight reports broken down by code?
