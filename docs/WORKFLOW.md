# RadIMO Medweb CSV Workflow

**Complete guide to the config-driven medweb CSV integration system**

---

## 📋 Overview

RadIMO uses a **config-driven architecture** to ingest medweb CSV schedules directly into the worker assignment system. This eliminates manual Excel file creation and provides flexible, maintainable activity-to-skill mappings.

**Key Benefits:**
- ✅ No manual Excel file creation
- ✅ Single CSV upload populates all modalities (CT/MR/XRAY)
- ✅ Config-based activity mappings (extensible without code changes)
- ✅ Per-worker skill overrides via worker_skill_roster
- ✅ Automatic daily preload at 7:30 AM
- ✅ Next-day schedule preparation interface
- ✅ Emergency force refresh capability

---

## 🔄 Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Medweb CSV Source                           │
│              (Monthly schedule from medweb)                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   Manual Upload   Auto-Preload   Force Refresh
   (any date)      (7:30 AM)      (emergency)
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  Config-Driven Parsing         │
        │  • medweb_mapping rules        │
        │  • shift_times calculation     │
        │  • worker_skill_roster apply   │
        └────────────────┬───────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  working_hours_df per modality │
        │  • CT: DataFrame               │
        │  • MR: DataFrame               │
        │  • XRAY: DataFrame             │
        └────────────────┬───────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  Optional Edit   │
              │  /prep-next-day  │
              └────────┬─────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   Real-Time Assignment       │
        │   • Load balancing           │
        │   • Fallback strategies      │
        │   • Ratio-based selection    │
        └──────────────────────────────┘
```

---

## 📤 Upload Strategies

### 1. **Manual Upload** (On-Demand)

**Use Case:** Upload schedule for a specific date immediately

**Steps:**
1. Navigate to **Admin Panel** (`/upload`)
2. Select **"📤 Medweb CSV Upload"** section
3. Choose CSV file
4. Select target date (can be today, tomorrow, or any future date)
5. Click **"⬆️ CSV Hochladen & Verarbeiten"**

**What Happens:**
- CSV is parsed for selected date
- Config rules applied (`medweb_mapping`)
- Worker roster overrides applied (`worker_skill_roster`)
- `working_hours_df` populated for all modalities
- Counters initialized (draw_counts, skill_counts, etc.)
- CSV saved as `uploads/master_medweb.csv` for future auto-preload

**When to Use:**
- Setting up system for first time
- Uploading updated schedule mid-day
- Loading schedule for specific date other than tomorrow
- Testing new config rules

---

### 2. **Auto-Preload** (Scheduled Daily)

**Use Case:** Automatically load next workday schedule every morning

**Schedule:** **7:30 AM CET** daily

**Next Workday Logic:**
- Monday-Thursday → Next day
- Friday → Monday (skip weekend)
- Holidays are NOT automatically skipped (manual intervention needed)

**What Happens:**
- Scheduler wakes up at 7:30 AM
- Checks for `uploads/master_medweb.csv`
- Calculates next workday
- Parses CSV for next workday date
- Applies config rules and roster overrides
- Populates `working_hours_df` for all modalities
- Initializes counters (fresh start for new day)
- Logs result to `selection.log`

**Requirements:**
- Master CSV must exist (`uploads/master_medweb.csv`)
- Master CSV should contain target date
- Application must be running at 7:30 AM

**Monitoring:**
Check `selection.log` for messages like:
```
2025-11-21 07:30:00 - INFO - Auto-preload successful: 2025-11-22, modalities=['ct', 'mr', 'xray'], workers=15
```

**If Auto-Preload Fails:**
- Check log: `selection.log`
- Verify master CSV exists and contains next workday data
- Manually upload via admin panel as fallback

---

### 3. **Preload Next Workday** (Manual Trigger)

**Use Case:** Manually preload tomorrow's schedule ahead of time

**Steps:**
1. Navigate to **Admin Panel** (`/upload`)
2. Select **"🔮 Preload Nächster Arbeitstag"** section
3. Choose updated CSV file
4. Click **"🔮 Nächsten Arbeitstag Preloaden"**
5. System shows next workday date (e.g., Friday shows Monday)

**What Happens:**
- Same as auto-preload, but triggered manually
- Useful for testing auto-preload behavior
- Updates master CSV for tomorrow's auto-preload

**When to Use:**
- Want to preload tonight for tomorrow
- Testing next-day workflow
- Updating tomorrow's schedule before 7:30 AM

---

### 4. **Force Refresh** (Emergency)

**Use Case:** Emergency same-day schedule reload (e.g., half the staff calls in sick)

**⚠️ WARNING:** This **destroys ALL assignment history** for the current day!

**Steps:**
1. Navigate to **Admin Panel** (`/upload`)
2. Select **"🔄 Force Refresh (Heute - NOTFALL)"** section
3. Choose updated CSV file
4. Read warning carefully
5. Confirm destruction of existing assignments
6. Click **"🔄 HEUTE Neu Laden (Notfall)"**

**What Happens:**
- All counters reset (draw_counts, skill_counts, WeightedCounts, etc.)
- All assignment history deleted
- New schedule loaded for TODAY
- Fresh start as if day just began
- Previous assignments NOT preserved

**When to Use:**
- Emergency staffing changes mid-day
- Critical errors in schedule discovered after 7:30 AM
- Major reorg of today's assignments needed

**⚠️ Use Sparingly:** This is intentionally destructive. For tomorrow's schedule, use prep page instead.

---

## 📝 Next-Day Schedule Preparation

### Overview

The prep page (`/prep-next-day`) provides an advanced edit interface for preparing tomorrow's schedule without affecting today's assignments.

**Access:** Admin Panel → **"📝 Nächsten Tag Bearbeiten"**

**Key Difference from Same-Day Editing:**
- **Same-day editing** (existing admin page): Preserves assignments, maintains distribution stability
- **Next-day prep**: Clean slate, full editing freedom, no assignment history to preserve

---

### Two Editing Modes

#### **Simple Mode** (Default) ✏️

**For:** Quick edits, fixing typos, adjusting times

**Features:**
- Click any cell to edit inline (spreadsheet UX)
- Edit worker names, times, skills, modifiers
- Changes tracked automatically
- Visual feedback: edited cells turn green
- All changes batched, saved together on "Save All"

**How to Use:**
1. Click modality tab (CT/MR/XRAY)
2. Click any cell
3. Type new value
4. Press Enter or click away
5. Cell turns green (pending change)
6. Repeat for all edits
7. Click **"💾 Alle Änderungen Speichern"**

**Editable Fields:**
- **PPL**: Worker name/abbreviation
- **Von/Bis**: Start/end times (HH:MM format)
- **Skills**: Click to cycle -1 → 0 → 1
- **Modifier**: Individual workload multiplier

**Skill Value Colors:**
- 🟢 Green (1): Active - primary + fallback
- 🟡 Yellow (0): Passive - fallback only
- 🔴 Red (-1): Excluded - never use

---

#### **Advanced Mode** (Power Users) 🔧

**For:** Structural changes, adding/removing workers

**Additional Features:**
- **Add Worker**: ➕ button adds new worker row
- **Delete Worker**: 🗑️ button per row (with confirmation)
- **Bulk Skill Set**: Set all workers' skill value for specific skill
- All simple mode features still available

**How to Use:**

**Add Worker:**
1. Click **"➕ Worker Hinzufügen"**
2. Enter worker name (e.g., "Neuer Worker (NW)")
3. Default values applied (Normal=1, Notfall=1, times=07:00-15:00)
4. Edit as needed
5. Save

**Delete Worker:**
1. Click 🗑️ next to worker row
2. Confirm deletion
3. Worker removed from tomorrow's schedule

**Bulk Skill Set:**
1. Click **"🔄 Bulk Skill Setzen"**
2. Enter skill name (e.g., "Msk")
3. Enter value (-1, 0, or 1)
4. All workers in current modality updated
5. Save

---

### Workflow Example

**Scenario:** Tomorrow's MR schedule has an error - one worker shouldn't do Notfall

**Simple Mode Approach:**
1. Navigate to `/prep-next-day`
2. Click **MR** tab
3. Find worker row
4. Click **Notfall** cell (shows "1")
5. Type "0" (passive) or "-1" (excluded)
6. Cell turns green
7. Click **"💾 Alle Änderungen Speichern"**
8. Done! Worker's Notfall set to fallback-only or excluded

**Alternative Advanced Mode:**
1. Same as above, but can also use **"🔄 Bulk Skill Setzen"**
2. Set Notfall=0 for ALL MR workers at once if needed

---

## ⚙️ Configuration

### Medweb Mapping Rules

Located in `config.yaml` under `medweb_mapping.rules`:

```yaml
medweb_mapping:
  rules:
    - match: "CT Spätdienst"          # Activity description substring
      modality: "ct"                   # Target modality (ct/mr/xray)
      shift: "Spaetdienst"            # Shift name (for time calculation)
      base_skills:                     # Default skill values
        Normal: 1                      # Active
        Notfall: 1                     # Active
        Privat: 0                      # Passive (fallback only)
        Herz: 0                        # Passive
        Msk: 0                         # Passive
        Chest: 0                       # Passive
```

**How Matching Works:**
- Case-insensitive substring matching
- First matching rule wins
- If no match, activity ignored (not SBZ-relevant)

**Example Matches:**
- "CT Spätdienst" matches "CT Spätdienst" ✅
- "SBZ: CT Spätdienst Zusatz" matches "CT Spätdienst" ✅
- "CT SPÄTDIENST" matches "CT Spätdienst" ✅
- "MR Assistent" does NOT match "CT Spätdienst" ❌

**Adding New Activity:**
1. Open `config.yaml`
2. Add new rule to `medweb_mapping.rules`
3. Save file
4. Restart application
5. No code changes needed!

---

### Shift Times

Located in `config.yaml` under `shift_times`:

```yaml
shift_times:
  Fruehdienst:
    default: "07:00-15:00"     # Monday-Thursday
    friday: "07:00-13:00"      # Friday shorter shift
  Spaetdienst:
    default: "13:00-21:00"     # Monday-Thursday
    friday: "13:00-19:00"      # Friday shorter shift
```

**How It Works:**
- Each mapping rule references a shift name
- System calculates times based on weekday
- Friday automatically uses shorter times
- Format: "HH:MM-HH:MM"

**Adding New Shift:**
```yaml
shift_times:
  Nachtdienst:
    default: "21:00-07:00"     # Overnight shift
    friday: "21:00-05:00"      # Shorter Friday night
```

---

### Worker Skill Roster

Located in `config.yaml` under `worker_skill_roster`:

```yaml
worker_skill_roster:
  AAn:  # Worker canonical ID (abbreviation from CSV)
    default:  # Applies to ALL modalities unless overridden
      Msk: 1      # This worker IS an MSK specialist

  AN:
    default:
      Chest: 1    # Chest specialist
    ct:           # CT-specific override
      Notfall: 0  # Only fallback for CT Notfall (not primary)
```

**Configuration Precedence:**
1. **Modality-specific override** (highest priority)
2. **Default override**
3. **Mapping rule base_skills**
4. **System defaults** (lowest priority)

**Example:**
```yaml
# Worker: KRUE, Modality: CT, Activity: "CT Assistent"

# Step 1: Mapping rule provides base_skills
base_skills: {Normal: 1, Notfall: 1, Herz: 0, ...}

# Step 2: Apply default roster overrides
worker_skill_roster.KRUE.default: {Chest: 1}  # KRUE is Chest specialist
→ {Normal: 1, Notfall: 1, Herz: 0, Chest: 1, ...}

# Step 3: Apply CT-specific overrides
worker_skill_roster.KRUE.ct: {Notfall: 0}  # Only fallback for CT Notfall
→ {Normal: 1, Notfall: 0, Herz: 0, Chest: 1, ...}  # Final skills
```

**When to Use:**
- Worker has special expertise (Msk, Chest, Herz specialist)
- Worker excluded from certain skills (e.g., first month → Notfall=-1)
- Worker only fallback for specific modality/skill combo

---

### Time Exclusions (NEW in v18)

Time exclusions **punch out time** from worker shifts for boards, meetings, teaching, etc.

Located in `config.yaml` under `medweb_mapping.rules`:

```yaml
medweb_mapping:
  rules:
    # Time exclusions - day-specific schedules
    - match: "Kopf-Hals-Board"
      exclusion: true
      schedule:
        Montag: "15:30-17:00"  # Only applies on Mondays
      prep_time:
        before: "30m"  # Prep: excludes 15:00-15:30
        after: "15m"   # Cleanup: excludes 17:00-17:15

    - match: "Board"
      exclusion: true
      schedule:
        Dienstag: "15:00-17:00"   # Different times per day
        Mittwoch: "10:00-12:00"
        Donnerstag: "14:00-16:00"

    - match: "Besprechung"
      exclusion: true
      schedule:
        Montag: "09:00-10:00"
        Mittwoch: "14:00-15:00"
        Freitag: "13:00-14:00"
```

**How It Works:**

1. **CSV Entry**: Worker has `"Kopf-Hals-Board"` in Beschreibung der Aktivität
2. **Weekday Check**: Is today in the schedule? (e.g., "Montag")
3. **Time Range**: Get schedule["Montag"] → "15:30-17:00"
4. **Prep Time**: Apply before/after extensions → 15:00-17:15
5. **Split Shift**: Worker's 07:00-21:00 becomes 07:00-15:00 + 17:15-21:00

**Example:**

```
CSV Entry (Monday):
"24.11.2025","NM","ZANDERCH","CZ","Charlotte Dr Zander",...,"Kopf-Hals-Board",...

Original Shift:    [07:00 ────────────────────────── 21:00]
Exclusion:                  [15:00 ────── 17:15]
                           (with prep time)

Result:            [07:00 ──── 15:00]  [17:15 ──── 21:00]
```

**Multiple Exclusions:**

System handles multiple overlapping exclusions per worker:

```
Original:    [07:00 ────────────────────────── 21:00]

Exclusions:
  Board:              [10:00 ── 12:00]
  Fortbildung:                    [15:00 ─── 17:00]

Result:      [07:00─10:00] [12:00─15:00] [17:00─21:00]
```

**Key Benefits:**
- ✅ Day-specific: Same activity, different times per weekday
- ✅ No parsing: Time in config, not CSV description
- ✅ Prep time: Automatic before/after extension
- ✅ Config-driven: Add new exclusions without code changes
- ✅ Flexible: Handles multiple overlapping exclusions

**Adding New Exclusion:**
1. Add rule to `medweb_mapping.rules` with `exclusion: true`
2. Define `schedule` with weekday-specific times
3. Optionally add `prep_time` (before/after)
4. Restart application

**Logging:**
```log
INFO: Time exclusion for Charlotte Dr Zander (CZ) (Montag): 15:00-17:15 (Kopf-Hals-Board)
INFO: Applying time exclusions for 3 workers on Montag
```

---

## 🔍 Troubleshooting

### CSV Upload Issues

**Problem:** "No data found for selected date"

**Causes:**
- CSV doesn't contain activities for that date
- Date format mismatch (should be DD.MM.YYYY in CSV)
- CSV encoding issues (should be comma or semicolon delimited, latin1 encoding)

**Solutions:**
- Verify CSV contains rows with target date in "Datum" column
- Check date format: "20.11.2025" not "2025-11-20"
- Try different date

---

**Problem:** "No workers loaded for any modality"

**Causes:**
- No medweb_mapping rules match activities in CSV
- All activities filtered out (not SBZ-relevant)
- Config syntax error

**Solutions:**
- Check `selection.log` for "No matching rule for activity: ..."
- Add new rules to `medweb_mapping.rules` for missing activities
- Validate config.yaml syntax (use YAML validator)

---

**Problem:** "Worker skills all zeros"

**Causes:**
- Mapping rule has base_skills all set to 0
- Worker in roster with all skills set to -1 or 0

**Solutions:**
- Check mapping rule: at least one skill should be 1
- Check worker_skill_roster: ensure not all excluded
- Review config precedence (roster overrides mapping)

---

### Auto-Preload Issues

**Problem:** Auto-preload didn't run

**Causes:**
- Application not running at 7:30 AM
- Master CSV doesn't exist
- Server clock incorrect
- Scheduler not initialized

**Solutions:**
- Check `selection.log` for auto-preload messages
- Verify `uploads/master_medweb.csv` exists
- Check server time: `date` (should be Europe/Berlin timezone)
- Restart application to reinitialize scheduler

---

**Problem:** Auto-preload failed with "No data for date"

**Causes:**
- Master CSV is old (doesn't contain next workday)
- Next workday is holiday (CSV doesn't have activities)

**Solutions:**
- Upload fresh CSV covering next few weeks
- Manually upload for specific date via admin panel
- Check CSV date range

---

### Prep Page Issues

**Problem:** Changes don't persist after save

**Causes:**
- Changes not actually saved (check for success message)
- Browser cached old data
- Server error during save

**Solutions:**
- Look for green "Änderungen gespeichert" message
- Hard refresh browser (Ctrl+Shift+R)
- Check browser console for errors
- Check `selection.log` for server errors

---

**Problem:** Can't delete worker (delete button missing)

**Causes:**
- Still in Simple Mode (delete only in Advanced Mode)

**Solutions:**
- Click **"🔧 Erweitert"** button to switch to Advanced Mode
- Delete button (🗑️) will appear next to each worker row

---

## 📊 Monitoring & Logs

### Selection Log

Located at: `selection.log`

**What's Logged:**
- Auto-preload results (success/failure, date, worker count)
- CSV upload operations
- Config rule matching
- Worker assignment operations
- Error messages and stack traces

**Example Log Entries:**
```
2025-11-21 07:30:00 - INFO - Auto-preload successful: 2025-11-22, modalities=['ct', 'mr', 'xray'], workers=15
2025-11-21 09:15:00 - WARNING - No matching rule for activity: "NUK Protokollieren"
2025-11-21 14:23:00 - INFO - Manual upload successful: 2025-11-23, workers={'ct': 5, 'mr': 6, 'xray': 4}
```

**Monitoring Auto-Preload:**
```bash
# Watch log in real-time
tail -f selection.log

# Check today's auto-preload
grep "Auto-preload" selection.log | grep "$(date +%Y-%m-%d)"

# Check for errors
grep "ERROR" selection.log | tail -20
```

---

### Admin Panel Status

**Check Current Schedule:**
1. Navigate to main interface (`/` or `/by-skill`)
2. View worker list for each modality
3. Check shift times displayed
4. Verify expected workers present

**Check Stats:**
- Draw counts per worker
- Skill-specific assignments
- Weighted counts
- Overflow indicators

---

## 🔐 Security & Access

### Admin Authentication

**Required for:**
- CSV upload operations
- Prep page access
- Force refresh
- Statistics viewing

**Credentials:**
- Username: `admin`
- Password: Set in `config.yaml` under `admin_credentials.password`

**⚠️ Change Default Password:**
```yaml
admin_credentials:
  password: "YOUR_SECURE_PASSWORD_HERE"  # Change this!
```

---

### Route Protection

**Public Routes:**
- `/` (main interface) - read-only assignment requests
- `/by-skill` - read-only skill-based view
- `/api/{modality}/{skill}` - assignment API (read-only counter updates)

**Admin Routes:**
- `/upload` - requires login
- `/prep-next-day` - requires login
- `/force-refresh-today` - requires login
- `/api/prep-next-day/*` - requires login

---

## 💡 Best Practices

### 1. **CSV Upload Strategy**

**Recommended:**
- Upload monthly CSV covering next 4-6 weeks
- Upload fresh CSV weekly (Friday afternoon for next week)
- Let auto-preload handle daily schedule loading
- Use prep page for corrections, not force refresh

**Avoid:**
- Uploading CSV daily manually (defeats auto-preload purpose)
- Using force refresh for tomorrow's schedule (use prep page)
- Forgetting to upload fresh CSV (auto-preload will fail)

---

### 2. **Config Management**

**Recommended:**
- Version control `config.yaml` (git commit after changes)
- Test config changes in dev environment first
- Document custom mapping rules (comments in YAML)
- Keep worker_skill_roster up to date

**Avoid:**
- Editing config while application running (restart needed)
- Syntax errors in YAML (validate before restart)
- Deleting mapping rules without checking impact

---

### 3. **Worker Roster Updates**

**When Workers Change:**
1. Add new workers to `worker_skill_roster` if they have special skills
2. Update existing workers if skills change
3. Remove workers who left (or set all skills to -1)
4. Restart application

**Don't Forget:**
- Worker canonical ID is abbreviation from CSV (e.g., "AM", "KRUE")
- Use `default` for skills that apply to all modalities
- Use modality keys (`ct`, `mr`, `xray`) for specific overrides

---

### 4. **Monitoring**

**Daily:**
- Check `selection.log` after 7:30 AM for auto-preload success
- Verify expected workers present in main interface
- Check for "No matching rule" warnings (indicates missing config)

**Weekly:**
- Review worker assignment patterns (balanced?)
- Check for fallback usage (excessive fallback = understaffed?)
- Upload fresh CSV for next week

---

### 5. **Backup**

**Important Files:**
- `config.yaml` - all configuration
- `uploads/master_medweb.csv` - current schedule source
- `selection.log` - operation history

**Backup Strategy:**
- Git commit `config.yaml` changes
- Keep copy of master CSV outside uploads/ folder
- Rotate logs weekly (compress old logs)

---

## 🚀 Migration from Excel Workflow

### Old Workflow (Deprecated)
```
medweb CSV → SBZDashboard → 3 Excel files → Manual upload per modality
```

### New Workflow
```
medweb CSV → RadIMO upload → Auto-preload → Done
```

### Migration Steps

**If you have Excel files:**
- Excel upload path has been removed (see [EXCEL_PATH_MIGRATION.md](EXCEL_PATH_MIGRATION.md))
- Backup commit: `e77525b` (see [BACKUP.md](../BACKUP.md) for rollback)
- To continue using Excel, rollback to backup commit

**Migrating to CSV:**
1. Obtain medweb CSV (monthly export)
2. Configure `medweb_mapping` rules for your activities
3. Configure `worker_skill_roster` for special workers
4. Upload CSV via admin panel (manual upload first time)
5. Verify schedule correct in main interface
6. Let auto-preload take over daily

**Configuration Migration:**
- Excel skill values (0/1) → medweb base_skills (-1/0/1)
- Excel Modifier column → worker modifiers (preserved)
- Excel TIME column → shift_times config
- Excel Tabelle2 (info texts) → maintain separately (not in CSV)

---

## 📚 Related Documentation

- **[README.md](../README.md)** - Overview, quick start, features
- **[INTEGRATION_COMPARISON.md](INTEGRATION_COMPARISON.md)** - Why config-driven approach was chosen
- **[EXCEL_PATH_MIGRATION.md](EXCEL_PATH_MIGRATION.md)** - Why Excel upload was removed
- **[SYSTEM_ANALYSIS.md](SYSTEM_ANALYSIS.md)** - Technical deep dive, balancing algorithms
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Testing strategies, edge cases

---

**Document Version:** 1.0
**Date:** November 2025
**Status:** Current
