# RadIMO Configuration Reference

Complete reference for `config.yaml` settings, synchronized with the current defaults.

---

## Overview

RadIMO uses a single `config.yaml` file for all configuration. Changes require application restart unless otherwise noted.

```yaml
# Main sections
admin_password: "..."           # Admin login
skill_roster_auto_import: true # Auto-add new workers to roster JSON
modalities: {...}               # CT, MR, XRAY, Mammo definitions
skills: {...}                   # Skill definitions, weights, UI ordering
...
```

---

## Global Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `admin_password` | string | `change_pw_for_live` | Password for all admin routes |
| `skill_roster_auto_import` | boolean | `true` | When loading CSV, auto-add missing workers to the Skill Matrix JSON |

---

## Scheduler Settings

Configure timings for automated background tasks.

```yaml
scheduler:
  daily_reset_time: "07:30"  # Time when Staked -> Live happens automatically
  auto_preload_time: 14      # Hour (0-23) when tomorrow's CSV is auto-loaded into staging
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `daily_reset_time` | string | `07:30` | Time format (HH:MM). Shifts the "Live" data to the new date. |
| `auto_preload_time` | integer | `14` | 24h format hour. Triggers automatic fetching of the next workday from the Master CSV. |

---

## Modalities

Define available modalities with display, weighting, and optional visibility filters.

```yaml
modalities:
  ct:
    label: CT              # Display name
    nav_color: '#1a5276'   # Navigation button color
    hover_color: '#153f5b' # Button hover color
    background_color: '#e6f2fa'  # Page background
    factor: 1.0            # Workload weight multiplier
  mr:
    label: MR
    nav_color: '#777777'
    hover_color: '#555555'
    background_color: '#f9f9f9'
    factor: 1.2            # MR work counts 20% more
  xray:
    label: XRAY
    nav_color: '#239b56'
    hover_color: '#1d7a48'
    background_color: '#e0f2e9'
    factor: 0.33           # XRAY work counts 1/3
  mammo:
    label: Mammo
    nav_color: '#e91e63'
    hover_color: '#c2185b'
    background_color: '#fce4ec'
    factor: 0.5            # Mammography counts half
    valid_skills: [Notfall, Privat, Gyn]  # Optional whitelist
    # hidden_skills: [MSK, Chest]         # Optional blacklist
```

**Factor**: Higher factor = work counts more toward weighted total. Use to balance effort across modalities.

**Visibility filters (optional):**
- `valid_skills`: only show these skills for the modality
- `hidden_skills`: hide these skills for the modality

---

## Skills

Define skills with weights, UI styling, and ordering.

```yaml
skills:
  Notfall:
    label: Notfall
    button_color: '#dc3545'
    text_color: '#ffffff'
    weight: 1.1
    optional: false
    special: false
    display_order: 0
    slug: notfall

  Privat:
    label: Privat
    button_color: '#ffc107'
    text_color: '#333333'
    weight: 1.2
    optional: true
    special: false
    display_order: 1
    slug: privat

  Gyn:
    label: Gyn
    button_color: '#e91e63'
    text_color: '#ffffff'
    weight: 1.0
    optional: true
    special: true
    # valid_modalities: [mammo, mr]  # Optional: only show on these modalities
    # hidden_modalities: [xray]      # Optional: hide on these modalities
    display_order: 2
    slug: gyn

  Päd:
    label: Päd
    button_color: '#4caf50'
    text_color: '#ffffff'
    weight: 1.0
    optional: true
    special: true
    display_order: 3
    slug: paed

  MSK:
    label: MSK
    button_color: '#9c27b0'
    text_color: '#ffffff'
    weight: 0.8
    optional: true
    special: true
    display_order: 4
    slug: msk

  Abdomen:
    label: Abdomen
    button_color: '#00bcd4'
    text_color: '#ffffff'
    weight: 1.0
    optional: true
    special: true
    always_visible: true  # If true, button stays even if no worker available
    display_order: 5
    slug: abdomen

  Chest:
    label: Chest
    button_color: '#ff9800'
    text_color: '#ffffff'
    weight: 0.8
    optional: true
    special: true
    display_order: 6
    slug: chest

  Cardvask:
    label: Cardvask
    button_color: '#28a745'
    text_color: '#ffffff'
    weight: 1.2
    optional: true
    special: true
    display_order: 7
    slug: cardvask

  Uro:
    label: Uro
    button_color: '#795548'
    text_color: '#ffffff'
    weight: 1.0
    optional: true
    special: true
    display_order: 8
    slug: uro
```

**Optional vs. special:**
- `optional: false` keeps the button visible even if no worker is active for the skill.
- `special: true` marks subspecialty buttons that can be hidden when no worker is available unless `optional: false`.

---

## Skill×Modality Weight Overrides

Override the default `skill_weight × modality_factor` calculation for specific combinations.

```yaml
skill_modality_overrides:
  mr:
    Cardvask: 1.8    # MR×Cardvask override
  # ct:
  #   Chest: 1.0     # Example override
```

**How it works:**
1. Check `skill_modality_overrides[modality][skill]` for explicit value
2. If not found, calculate: `skill_weight × modality_factor`

**Use cases:**
- Cardiac MR is more demanding → increase MR×Cardvask weight
- XRAY MSK is simpler → decrease XRAY×MSK weight
- Fine-tune fairness for specialty combinations

---

## Skill Value Colors

How skill values appear in the prep page table.

```yaml
skill_value_colors:
  active:     # skill = 1 (primary assignment)
    color: '#28a745'
    label: 'Active'
  passive:    # skill = 0 (fallback only)
    color: '#6c757d'
    label: 'Passive'
  excluded:   # skill = -1 (never assign)
    color: '#dc3545'
    label: 'Excluded'
  weighted:   # skill = 'w' (assisted/weighted)
    color: '#17a2b8'
    label: 'Weighted'
```

---

## Skill Value Hierarchy & Overwrite Logic

This section documents how skill values (`-1`, `0`, `1`, `w`) are resolved across the system.

### Skill Value Meanings

| Value | Name | Meaning | Balancer Behavior |
|-------|------|---------|-------------------|
| `-1` | **Excluded** | Worker cannot perform this skill/modality | Filtered out entirely - never receives work |
| `0` | **Generalist** | Worker CAN do this work as backup | Fallback pool - only receives work when specialists overloaded |
| `1` | **Specialist** | Worker is trained for this work | Priority assignment, uses modifier=1.0 |
| `w` | **Weighted** | Worker is in training/assisted | Priority assignment, uses personal modifier (reduced workload) |

### Value Sources (Priority Order)

1. **Skill Roster** (`worker_skill_roster.json`) - baseline per-worker skill settings
2. **CSV Mapping Rules** (`skill_overrides` in config) - shift-specific overrides
3. **Prep Page Edits** - manual daily adjustments

### Overwrite Rules During CSV Loading

When CSV mapping rules apply `skill_overrides` to a worker's roster values:

| Roster Value | CSV Override | Result | Explanation |
|--------------|--------------|--------|-------------|
| `-1` | any | `-1` | **Roster `-1` always wins** - hard exclusions cannot be overridden |
| `w` | `1` | `w` | Worker stays weighted (CSV assigns them, they stay in training mode) |
| `w` | `0` | `-1` | Not explicitly assigned to team → **excluded** (not helper) |
| `w` | `-1` | `-1` | Explicit exclusion from CSV |
| `w` | *(no match)* | `-1` | Not on any shift for this skill → **excluded** |
| `1` | any | CSV value | Normal override |
| `0` | any | CSV value | Normal override |

**Key insight:** Workers with roster `w` are only included when explicitly assigned via CSV (`skill_overrides: 1`). If not assigned, they become `-1` (excluded), not `0` (helper). This prevents trainees from accidentally being assigned to teams they're not part of.

### Overwrite Rules During Prep/UI Edits

Manual edits in the prep page can change any value:

- No restrictions - allows daily flexibility
- Can change `-1` → `w`/`1`/`0` (e.g., adding someone new to a team)
- Can change `w` → `1` (promoting from training to full)
- Changes persist only for that day's schedule

### Modifier Priority

When a worker has skill=`w`, the system uses their personal modifier to reduce their workload:

```
Priority: Shift Modifier > Roster Modifier > Default (1.0)
```

| Source | When Used |
|--------|-----------|
| **Shift Modifier** | If shift explicitly sets `Modifier ≠ 1.0` |
| **Roster Modifier** | If shift modifier is default (1.0), use roster's `modifier` field |
| **Default** | If neither is set, use `1.0` |

**Roster modifier setup:**

In the Skill Roster page, each worker has a global `modifier` field:
- `1.0` = normal workload (default)
- `0.5` = 50% workload (trainee)
- `0.75` = 75% workload (experienced but supported)

The modifier affects weighted (`w`) assignments by adjusting the workload calculation:
```
weight = base_weight × (1.0 / modifier)
```

Example: modifier=0.5 means each assignment counts double toward the worker's total, effectively halving their workload.

---

## UI Colors

Top-level UI theme settings.

```yaml
ui_colors:
  today_tab: '#28a745'        # Green for "Change Today"
  tomorrow_tab: '#ffc107'     # Yellow for "Prep Tomorrow"
  success: '#28a745'
  error: '#dc3545'
  warning: '#ffc107'
  info: '#17a2b8'
```

---

## Balancer Settings

Control load balancing behavior and hours counting.

```yaml
balancer:
  enabled: true
  min_assignments_per_skill: 5    # Minimum weighted assignments
  imbalance_threshold_pct: 30     # Trigger fallback at 30% imbalance
  allow_fallback_on_imbalance: true
  disable_overflow_at_shift_end_minutes: 30  # Don't assign overflow in last X minutes

  # Hours counting for workload calculation
  hours_counting:
    shift_default: true   # type: "shift" entries count towards hours (default)
    gap_default: false    # type: "gap" entries don't count towards hours (default)

  # Exclusion-based routing configuration
  # Define which workers to EXCLUDE when requesting each skill
  # Workers with excluded_skill=1 won't receive work for this skill
  # Format (shortcut style - supports skill, modality, or skill_mod combos):
  #   skill: []                    # No exclusions
  #   skill: [skill1]              # Exclude workers with skill1=1 (all modalities)
  #   skill: [skill1, skill2]      # Exclude workers with skill1=1 OR skill2=1
  #   skill_mod: [skill1_mod]      # Exclude specific combo (e.g., cardvask_ct: [msk_ct])
  #   mod: [skill1]                # Modality-wide (all *_mod skills exclude skill1)
  exclude_skills:
    notfall: []      # No exclusions
    privat: []
    gyn: []
    paed: []
    msk: []
    abdomen: []
    chest: []
    cardvask: []     # Example: cardvask: [msk] means cardvask work excludes MSK specialists
    uro: []
```

### Specialist-First Assignment with Pooled Worker Overflow

The system prioritizes specialists while using pooled workers (skill=0) as backup capacity within each modality:

**Assignment Strategy:**

1. **Filter workers in requested modality:**
   - Include workers with skill≥0 (excludes skill=-1)
   - Apply shift start/end buffers (per-worker per-shift)
   - Apply exclusion rules (e.g., notfall_ct team won't get mammo_gyn)

2. **Split into pools:**
   - **Specialists:** skill=1 or 'w' (trained for this work)
   - **Generalists:** skill=0 (trained in modality, can help when needed)

3. **Minimum balancer (fair distribution among specialists):**
   - Ensure all specialists get minimum weighted assignments before overflow
   - Prevents strange effects at start of day

4. **Specialist-first selection with imbalance overflow:**
   - Calculate workload ratio for each worker (weighted_count / hours_worked)
   - If hours_worked is 0, ratios are treated as 0 when weighted_count is 0, or very high when weighted_count exists
   - Compare min_specialist_ratio vs min_generalist_ratio
   - If imbalance ≥ threshold% (normalized against the higher pool average): overflow to generalist with lowest ratio
   - Otherwise: assign to specialist with lowest ratio

5. **Fallback without exclusions:**
   - If no workers available after exclusions, retry without exclusion filters
   - Maintains specialist-first logic

**Configuration:**
```yaml
balancer:
  min_assignments_per_skill: 3             # All specialists get 3 weighted assignments before overflow
  imbalance_threshold_pct: 30              # Overflow when specialists 30%+ more loaded than generalists
  disable_overflow_at_shift_start_minutes: 15  # Don't assign overflow in first 15min of shift
  disable_overflow_at_shift_end_minutes: 30    # Don't assign overflow in last 30min of shift
  exclude_skills:
    cardvask: [msk]  # MSK specialists won't get Cardvask work unless no one else available
```

### Two-Phase Minimum Balancer

**Phase 1 (No-Overflow):** Until all ACTIVE workers (skill ≥ 1) reach minimum weighted assignments, restrict pool to underutilized workers.

**Phase 2 (Normal Mode):** Once all active workers have minimum, allow normal weighted overflow.

---

## Vendor Mappings (Medweb CSV)

Map activity descriptions from vendor CSV files to shifts and gaps. The current implementation uses **vendor_mappings** with a unified structure where times are embedded directly in each rule.

```yaml
vendor_mappings:
  medweb:
    # Column name mappings for this vendor
    columns:
      date: "Datum"
      activity: "Beschreibung der Aktivität"
      employee_name: "Name des Mitarbeiters"
      employee_code: "Code des Mitarbeiters"
      day_part: "Tageszeit"  # Optional: VM/NM split heuristic

    # Rules for mapping activities to shifts/gaps
    # Rules are evaluated in order; first match wins
    rules:
    # ===========================================
    # SHIFTS - Work assignments with times and skill_overrides
    # ===========================================

    # CT Shifts
    - match: "CT Spätdienst"
      type: "shift"
      times:
        default: "13:00-21:00"
        Freitag: "13:00-19:00"
      skill_overrides:
        Notfall_ct: 1
        Privat_ct: 1
        MSK_ct: 0
        Abdomen_ct: 0
        Chest_ct: 0
        Cardvask_ct: 0
        Uro_ct: 0
        Gyn_ct: 0
        Päd_ct: 0

    - match: "CT Assistent"
      type: "shift"
      times:
        default: "07:00-15:00"
        Freitag: "07:00-13:00"
      skill_overrides:
        Notfall_ct: 1
        Privat_ct: 1
        MSK_ct: 0

    # Weighted entry (beginner/assisted worker)
    - match: "MR Assistent 1. Monat"
      type: "shift"
      times:
        default: "07:00-15:00"
        Freitag: "07:00-13:00"
      modifier: 0.5  # Beginner: counts double toward their load
      skill_overrides:
        Notfall_mr: w
        Privat_mr: 0

    # Multi-modality team
    - match: "MSK Team"
      type: "shift"
      times:
        default: "07:00-15:00"
        Freitag: "07:00-13:00"
      skill_overrides:
        MSK_ct: 1
        MSK_mr: 1
        MSK_xray: 1

    # Administrative shift that doesn't count toward load balancing
    - match: "Cortex Aufklärung"
      type: "shift"
      times:
        default: "07:00-15:00"
        Freitag: "07:00-13:00"
      label: "Aufklärung"
      counts_for_hours: false  # Administrative task
      skill_overrides:
        Notfall_ct: 0  # Minimal skill, just to have a modality

    # ===========================================
    # GAPS - Time exclusions (worker unavailable)
    # ===========================================

    - match: "Kopf-Hals-Board"
      type: "gap"
      times:
        Montag:
          - "15:30-17:00"
      skill_overrides:
        all: -1

    - match: "Board"
      type: "gap"
      times:
        Dienstag:
          - "15:00-17:00"
        Mittwoch:
          - "10:00-12:00"
        Donnerstag:
          - "14:00-16:00"
      skill_overrides:
        all: -1
```

### Rule Matching

**First match wins.** Order rules from specific to general.

### Skill Override Shortcuts

The `skill_overrides` field supports shortcuts:
- `all: -1` → all Skill×Modality combinations = -1
- `MSK: 1` → all MSK_* combinations = 1 (MSK_ct, MSK_mr, etc.)
- `ct: 1` → all *_ct combinations = 1 (Notfall_ct, MSK_ct, etc.)

### Weighted/Assisted Workers

Use `skill_overrides: {Skill_mod: w}` plus a `modifier` (0.5–1.5):
```yaml
- match: "MSK Anfänger"
  modifier: 0.5  # Beginner: counts double toward their load
  skill_overrides:
    MSK_ct: w
    MSK_xray: w
```

### Hours Counting

- **Shifts** count toward workload unless `counts_for_hours: false`
- **Gaps** do NOT count toward workload (defaults from `balancer.hours_counting`)

### Day-Specific Times

Times support day-specific overrides:
- `default`: Monday-Thursday (or all days if no day-specific override)
- `Montag`, `Dienstag`, `Mittwoch`, `Donnerstag`, `Freitag`: Day overrides

Gaps support multiple time blocks per day (arrays):
```yaml
times:
  Montag:
    - "10:00-11:00"
    - "14:00-15:00"
```

---

## Worker Skill Matrix

Defines Skill×Modality combinations for each worker. The worker roster is stored in `worker_skill_roster.json` and can be edited via the Skill Matrix admin page (`/skill-roster`).

**Format:** `"skill_modality": value` (e.g., `"MSK_ct": 1`)

Both `"skill_modality"` and `"modality_skill"` formats are accepted and normalized automatically.

### Example (worker_skill_roster.json)

```json
{
  "AA": {
    "MSK_ct": 1,
    "MSK_mr": 1,
    "MSK_xray": 1,
    "MSK_mammo": 0,
    "Notfall_ct": 1,
    "Notfall_mr": 1,
    "Notfall_xray": 1,
    "Notfall_mammo": 0
  },
  "DEMO1": {
    "Cardvask_ct": 1,
    "Cardvask_mr": 1,
    "Notfall_ct": 1,
    "Notfall_mr": 1,
    "MSK_ct": -1,
    "MSK_mr": -1,
    "Chest_ct": -1
  },
  "MSK_ANFAENGER": {
    "MSK_ct": "w",
    "MSK_xray": "w",
    "MSK_mr": 0
  }
}
```

### Value Legend

- `1` = **Active** - primary assignment + fallback
- `0` = **Passive** - fallback only (generalist pool)
- `-1` = **Hard exclude** - cannot be overridden by vendor CSV rules
- `"w"` = **Weighted** - assisted/learning (combine with `modifier` in vendor rules)

### Override Precedence

When combining roster values with vendor CSV `skill_overrides`:

1. **Worker roster** - baseline for all Skill×Modality pairs
2. **Vendor rule skill_overrides** - overrides only specified combinations
3. **Roster -1 (hard exclude)** - always wins, cannot be overridden

**Example:**
- Worker roster: `{"MSK_ct": 1, "MSK_mr": 1, "Gyn_ct": 0, "Gyn_mr": 0}`
- CSV rule assigns "Gyn Team" with `skill_overrides: {"Gyn_ct": 1, "Gyn_mr": 1}`
- Result: Gyn → 1, MSK → 1 (both active for this worker on this day)
- If roster had `"MSK_ct": -1`, it stays -1 (hard exclude wins)

---

## Complete Example

```yaml
admin_password: change_for_production
skill_roster_auto_import: true

modalities:
  ct:
    label: CT
    nav_color: '#1a5276'
    factor: 1.0
  mr:
    label: MR
    nav_color: '#777777'
    factor: 1.2
  xray:
    label: X-ray
    nav_color: '#239b56'
    factor: 0.33
  mammo:
    label: Mammo
    nav_color: '#e91e63'
    factor: 0.5
    valid_skills: [Notfall, Privat, Gyn]

skills:
  Notfall:
    label: Notfall
    weight: 1.1
    optional: false
    display_order: 0
  Privat:
    label: Privat
    weight: 1.2
    optional: true
    display_order: 1
  Cardvask:
    label: Cardvask
    weight: 1.2
    optional: true
    special: true
    display_order: 7

skill_modality_overrides:
  mr:
    Cardvask: 1.8  # MR cardiac work weighted higher

balancer:
  enabled: true
  min_assignments_per_skill: 3
  imbalance_threshold_pct: 30
  allow_fallback_on_imbalance: true
  disable_overflow_at_shift_start_minutes: 15
  disable_overflow_at_shift_end_minutes: 30
  hours_counting:
    shift_default: true
    gap_default: false
  exclude_skills:
    cardvask: [msk]
    notfall: []

vendor_mappings:
  medweb:
    columns:
      date: "Datum"
      activity: "Beschreibung der Aktivität"
      employee_name: "Name des Mitarbeiters"
      employee_code: "Code des Mitarbeiters"
    rules:
      - match: "CT Assistent"
        type: "shift"
        times:
          default: "07:00-15:00"
          Freitag: "07:00-13:00"
        skill_overrides:
          Notfall_ct: 1
          Privat_ct: 0
          Cardvask_ct: 0
      - match: "Kopf-Hals-Board"
        type: "gap"
        times:
          Montag:
            - "15:30-17:00"
        skill_overrides:
          all: -1
```

**Note:** Worker skill roster is stored in `worker_skill_roster.json` (not in config.yaml). See Worker Skill Matrix section above for format.

---

## Tips

1. **Adding new activity**: Add rule to `vendor_mappings.medweb.rules`, restart app
2. **Adjusting worker skills**: Use the Skill Matrix admin page (`/skill-roster`) or edit `worker_skill_roster.json` directly
3. **Fine-tuning balance**: Adjust `skill_modality_overrides` for specific combinations
4. **Testing config**: Run `python scripts/ops_check.py` to validate
5. **Generating rules from CSV**: Use `python scripts/prepare_config.py --input <csv>` to bootstrap vendor mapping rules
