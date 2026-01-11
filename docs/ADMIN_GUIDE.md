# RadIMO Admin Guide

Guide to the admin system for managing workers and schedules.

---

## Overview

RadIMO provides three admin entry points for different operational needs:

| Page | URL | Effect | Use Case |
|------|-----|--------|----------|
| **Skill Matrix** | `/skill-roster` | Direct | Permanent skill management |
| **Schedule Edit (Today)** | `/prep-next-day` | Live | Same-day adjustments (Live Edit) |
| **Schedule Edit (Tomorrow)** | `/prep-next-day` | Staged | Daily schedule preparation |

All admin pages require login with the admin password from `config.yaml`.

---

## Workflow Separation

┌─────────────────────────────────────────────────────────────┐
│  SKILL MATRIX (Permanent)        /skill-roster              │
│  ├─ Multi-modality grid                                     │
│  ├─ Edit skill values (-1, 0, 1, w) + global modifier       │
│  └─ Save directly to roster JSON                            │
├─────────────────────────────────────────────────────────────┤
│  SCHEDULE EDIT                  /prep-next-day              │
│  ├─ EDIT TODAY:           Immediate live changes            │
│  │  └─ Adjust times, add/remove workers, split shifts       │
│  ├─ PREP TOMORROW:        Stage for next workday            │
│  │  └─ Prepare tomorrow's setup from Master CSV             │
│  └─ Both modes: Interactive GAP handling (Split Shift)      │
└─────────────────────────────────────────────────────────────┘

---

## Skill Matrix (`/skill-roster`)

**Purpose:** Manage permanent worker skills across CT, MR, X-ray, and Mammo.

**Key behavior:** Changes save directly to `worker_skill_roster.json` and take effect on the next reload/assignment.

### How It Works

1. Navigate to `/skill-roster` (or "Skill Matrix" in nav)
2. Select worker from the side list
3. Edit skill values in the grid:
   - **1** = Active (Assigned) - 🟢 Green
   - **w** = Weighted (Training/Assisted) - 🔵 Blue
   - **0** = Passive (Helper/Fallback) - 🟡 Yellow
   - **-1** = Excluded (Never) - 🔴 Red
4. Set **Global Modifier** for weighted workers:
   - `1.0` = normal workload (default)
   - `0.5` = 50% workload (trainee - gets half the assignments)
   - `0.75` = 75% workload (experienced but supervised)
5. Click **"Save"** to persist changes.
6. Use **"Import new workers"** to pull workers from current schedules who are missing from the roster.

**Important:** Workers with `w` in the roster are only included in a shift if the CSV mapping explicitly assigns them (`skill_overrides: 1`). Otherwise they become `-1` (excluded). This prevents trainees from appearing on teams they're not assigned to.

See [CONFIGURATION.md](CONFIGURATION.md#skill-value-hierarchy--overwrite-logic) for detailed overwrite rules.

### Example: MSK/Haut Rotation
To make "AM" an MSK/Haut specialist (key: `msk-haut`):
1. Select "AM"
2. Change MSK/Haut column in MR/CT to `1`
3. Click "Save"

---

## Schedule Edit (`/prep-next-day`)

**Purpose:** Edit schedules with two modes: "Edit Today" for immediate live changes, or "Prep Tomorrow" for planning.

**Key behavior:** Shared interface with modality tabs (CT/MR/XRAY/MAMMO).
- **Edit Today**: Immediate effect on live assignment pool.
- **Prep Tomorrow**: Stages changes for the next workday's auto-preload.

### When to Use

**Edit Today:**
- Worker call-ins or sick leave adjustments.
- Urgent time shifts for today's workers.
- Add/Remove workers from the current live rotation.

**Prep Tomorrow:**
- Daily preparation based on the Master CSV.
- Adjusting Tomorrow's schedule before it goes live.

### Interface Components

Both tabs share the same editing interface with modality-specific tables:

#### Data Loading
Each mode allows rebuilding from the master data:
- **"Load Today"**: Rebuilds today's live schedule from `master_medweb.csv`.
- **"Preload Tomorrow"**: Rebuilds tomorrow's staged schedule from `master_medweb.csv`.

#### Interactive Grid
- **Inline Edit**: Click any cell (Start, End, Skill, Modifier) to edit.
- **GAP Handling**: Use the "Add Gap" button to split a shift (e.g., for a 1-hour board meeting).
- **Advanced Mode**: Toggle to Add/Delete worker rows.

#### Filtering Controls

Both tabs include smart filters:
- **Modality filter**: Show only specific modality (CT/MR/XRAY/Mammo)
- **Skill filter**: Show only workers with specific skill active
- **Hide 0/-1 checkbox**: Hide workers with passive/excluded values for cleaner view

### Editable Fields

| Field | Format | Example |
|-------|--------|---------|
| Worker | Text | "Dr. Müller (AM)" |
| Start Time | HH:MM | "07:00" |
| End Time | HH:MM | "15:00" |
| Skills | -1, 0, 1, w | 1 (active) |
| Modifier | 0.5-1.5 | 1.0 |

### Skill Value Colors

- 🟢 **Green (1)** = Active specialist (Modifier NOT applied)
- 🟡 **Yellow (0)** = Passive/Fallback
- 🔴 **Red (-1)** = Excluded
- 🔵 **Blue (w)** = Weighted/learning (Modifier IS applied)

### Example Workflows

#### Fix Wrong Shift Time (Same Day)

**Scenario:** Worker "MS" has wrong start time TODAY.

1. Go to `/prep-next-day`
2. Click **"Change Today"** tab (green header)
3. Select modality tab (CT/MR/XRAY)
4. Find "MS" in table
5. Click start_time cell, change to correct time
6. Click "Save Changes" → **Immediate effect**

#### Prepare Tomorrow's Schedule

**Scenario:** Plan tomorrow's coverage in advance.

1. Go to `/prep-next-day`
2. Click **"Prep Tomorrow"** tab (yellow header)
3. Click "Load Tomorrow" to load auto-generated schedule
4. Make adjustments as needed
5. Click "Save Changes" → Applied at next auto-preload (7:30 AM)

---

## Admin Panel (`/upload`)

Central hub for Master CSV management and system health.

### Available Actions

| Action | Description |
|--------|-------------|
| **Master CSV Upload** | Upload monthly medweb export (powers everything) |
| **Load Today** | Rebuild today's live schedule from Master (Resets counters) |
| **Preload Tomorrow** | Prepare tomorrow's staged schedule from Master |

### Workflow Strategy

1. **Upload Master CSV**: Once per month or whenever the master schedule changes.
2. **Daily Reset**: Automated at 07:30 CET, or manual via "Load Today".
3. **Daily Prep**: Use "Schedule Edit" -> "Prep Tomorrow" in the evening for the next day.

---

## Best Practices

### Daily Operations

1. **Morning:** Check auto-preload succeeded (view `/timetable`)
2. **During day:** Use assignment interface (`/` or `/by-skill`)
3. **Same-day adjustments:** Use `/prep-next-day` → **"Change Today"** tab (immediate effect, counters preserved)
4. **End of day:** Review assignments, plan tomorrow via `/prep-next-day` → **"Prep Tomorrow"** tab

### Planning Rotations

1. Update `config.yaml` or `/skill-roster` with new skills
2. Save to staging
3. Test with `/prep-next-day` → "Prep Tomorrow" tab preview
4. Activate on rotation start day

### Same-Day Changes

**Option 1: Incremental Changes (Recommended)**
- Use `/prep-next-day` → **"Change Today"** tab
- Preserves all assignment counters and history
- Immediate effect on schedule
- Use for: worker additions, time adjustments, skill corrections

**Option 2: Full Schedule Rebuild (Use with Caution)**
- Use Admin Panel → "Force Refresh Today"
- **WARNING:** Destroys ALL counters and assignment history
- Only use when schedule structure fundamentally changes
- Document reason and time of refresh

### Skill Management

| Change Type | Use This |
|-------------|----------|
| Permanent skill change | `config.yaml` → `worker_skill_roster` |
| Temporary/rotation change | `/skill_roster` staging |
| Same-day schedule edit | `/prep-next-day` → "Change Today" tab |
| Tomorrow schedule prep | `/prep-next-day` → "Prep Tomorrow" tab |

---

## Troubleshooting

### Auto-preload didn't run

1. Check `selection.log` for errors
2. Verify master CSV exists in `uploads/`
3. Confirm application was running at 07:30 CET
4. Manual trigger: Use admin panel "Preload Next Workday"

### Worker missing from schedule

1. Check medweb CSV has correct date entry
2. Verify `medweb_mapping` rules match activity
3. Check `worker_skill_roster` for exclusions (-1)
4. Review `/prep-next-day` → check both "Change Today" and "Prep Tomorrow" tabs for manual deletions

### Skill changes not taking effect

1. Verify changes were saved (not just edited)
2. Skill Matrix changes take effect on next reload/assignment
3. Restart application if changed `config.yaml`

### Assignment not balanced

1. Check worker modifiers
2. Review `skill_modality_overrides` for weight tweaks
3. Verify `min_assignments_per_skill` setting
4. Check imbalance threshold (default 30%)
