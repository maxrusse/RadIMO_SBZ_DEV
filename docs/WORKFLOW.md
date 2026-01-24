- A single **Master CSV** upload populates current and future workday schedules.
- Mapping rules attach modality, shift, and skill overrides to activity descriptions.
- **GAP handling**: meetings and boards trigger split shifts, keeping coverage aligned with availability.
- **Skill management**: workers pull global skill levels from the Skill Matrix (saves directly).
- **Daily prep**: admins use "Prep Tomorrow" to adjust the staged schedule for the next workday.

---

## 🔄 Complete Flow

1) **Source**: medweb exports a monthly CSV with worker activities.
2) **Ingestion**: the CSV is uploaded once as the master copy; it powers both manual processing and the daily preload.
3) **Parsing**: mapping rules attach modality and shift names; shift times come from the config with Friday-specific exceptions when defined.
4) **Normalization**: shift windows become start/end datetimes. Durations are calculated for same-day shifts only (end time must be after start time).
5) **Exclusions**: scheduled boards or meetings split shifts into available segments without losing total coverage accounting.
6) **Rosters**: worker skills load from flat Skill×Modality combinations in the roster; CSV rule skill_overrides can override specific combinations.
7) **Preparation**: optional edits for the next workday happen on `/prep-tomorrow`, keeping current-day assignments untouched.
8) **Assignment**: real-time selection uses the normalized shifts and skill values to balance workload and honor fallback rules.

---

## 📤 Master CSV Strategy

RadIMO uses a single monthly CSV (`master_medweb.csv`) to power the entire schedule.

### 1. Upload Master
**Action**: Admin Panel -> **Master CSV Upload**
- Saves the file to `uploads/master_medweb.csv`.
- This file acts as the source of truth for "Load Today" and "Preload Tomorrow".

### 2. Daily Operations
**Action**: Admin Panel -> **Load Today**
- Manually trigger a rebuild of today's schedule from the Master CSV.
- **WARNING**: This resets all current assignment counters and history.

### 3. Future Planning
**Action**: Admin Panel -> **Preload Tomorrow**
- Fetches the next workday's data from the Master CSV.
- Populates the "Prep Tomorrow" view in Schedule Edit.

### 4. Automated Reset
- Every morning at the **configured time** (default 07:30 CET), the system automatically performs the "Load Today" logic for the new date.

---

## 📝 Schedule Editing (`/prep-today`, `/prep-tomorrow`)

Admins can adjust "Today" (Live) or plan "Tomorrow" (Staged) via separate pages.

**Features:**
- **Manual highlighting**: Any shifts added or edited manually by an admin are highlighted (subtle yellow) to distinguish them from auto-loaded Master CSV data.
- **Gaps as segments**: Gaps (meetings, breaks, boards) are stored as `gap_segment` rows, and shifts are split into `shift_segment` availability windows. Gaps always win over shifts, so availability comes only from `shift_segment` rows.
- **Effective duration**: Each shift segment includes its own duration, and gap segments never contribute to availability or hours.

---

## ⚙️ Configuration Notes

- **Mapping rules**: First match wins. Order from specific to general.
- **Same-day shifts**: All shifts must have end time after start time on the same day.
- **Skill roster**: Saves directly to `worker_skill_roster.json`; priority over mapping defaults.

---

## ✅ Quick Checklist

- [ ] Upload Master CSV at start of month.
- [ ] Review "Prep Tomorrow" in the evening (`/prep-tomorrow`).
- [ ] Use "Change Today" for same-day sickness/changes (`/prep-today`).
- [ ] Monitor `selection.log` for auto-reset confirmation at 07:30.
