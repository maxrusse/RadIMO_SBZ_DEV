# RadIMO Cortex

**Intelligent Radiology Orchestration**

Worker assignment for radiology teams with automatic load balancing, skill-aware routing, and shift-based fairness.

---

## What is RadIMO Cortex?

RadIMO Cortex orchestrates workload distribution for radiology teams across multiple modalities (CT, MR, XRAY, Mammo) and skills (Notfall, Privat, Gyn, Päd, MSK/Haut, Abd/Onco, Card/Thor, Uro, Kopf/Hals). It balances assignments for fairness while respecting availability, shift timing, and skill levels.

**Key capabilities:**
- Real-time worker assignment with automatic load balancing
- Skill-based routing with configurable exclusion rules
- Dynamic shift handling with work-hour-adjusted balancing
- Two UI modes: by modality or by skill
- Two-level fallback for high availability
- Master CSV integration for monthly schedule management
- Admin system: Skill Matrix (direct save), Schedule Edit (Today + Prep Tomorrow)
- Worker skill roster admin portal with simplified JSON management
- GAP handling (split shifts) for meetings and boards
- Smart skill filtering on Schedule Edit and Timetable views
- Special tasks for custom sub-workflows with separate tracking

---

## Quick Start

### Installation

```bash
pip install -r requirements.txt
python scripts/ops_check.py  # Check system readiness
flask --app app run --debug  # Start application
```

### Access Points

**Operational pages (access-protected if enabled):**
| Page | URL | Description |
|------|-----|-------------|
| Main Interface | `/` | Assignment by modality (CT/MR/XRAY) |
| Skill View | `/by-skill` | Assignment by skill (Notfall, Card/Thor, MSK/Haut, etc.) |
| Timetable | `/timetable` | Visualize shifts and schedules |

If basic access protection is enabled, users authenticate via `/access-login` before reaching the operational pages.

**Admin pages (password protected when enabled):**
| Page | URL | Description |
|------|-----|-------------|
| Admin Panel | `/upload` | Master CSV management, stats, system health |
| Skill Matrix | `/skill-roster` | Edit worker skills (Direct Save) |
| Schedule Edit (Today) | `/prep-today` | Edit today (live) |
| Schedule Edit (Tomorrow) | `/prep-tomorrow` | Prep tomorrow (staged) |
| Worker Load | `/worker-load` | Load monitoring dashboard |
| Weight Matrix | `/button-weights` | Configure button weights and special tasks |

---

## Core Workflow

Master CSV (monthly schedule)
    ↓
Upload via /upload (Master CSV)
    ↓
Load Today (Live) or Preload Tomorrow (Staged)
    ↓
Config-driven parsing (medweb_mapping rules)
    ↓
Apply worker_skill_roster overrides
    ↓
Build working_hours_df per modality
    ↓
Real-time assignment with load balancing

---

## Key Features

### Smart Load Balancing
- **Skill-based routing** with configurable exclusion rules
- **Work-hour adjusted ratios** ensure fair distribution
- **Two-level fallback** system for high availability
- See [CONFIGURATION.md](docs/CONFIGURATION.md) for routing details

### Skill System
| Value | Name | Behavior |
|-------|------|----------|
| **w** | Weighted | Assisted/learning worker - uses personal Modifier for load calculation |
| **1** | Active | Primary routing - actively performs this skill (Modifier NOT applied) |
| **0** | Passive | Fallback only - can help if needed |
| **-1** | Excluded | Never assigned - cannot do this skill |

### Weighting System
Assignments are weighted by:
- **Skill weight**: e.g., Notfall=1.1, Privat=1.2
- **Modality factor**: e.g., MR=1.2, XRAY=0.33
- **Worker modifier**: Individual multiplier (only applied when skill='w')
- **Skill×Modality overrides**: Custom weights for specific combinations

### Admin Pages
1. **Skill Matrix** (`/skill-roster`) - Edit worker skills across modalities (saves directly)
2. **Schedule Edit (Today)** (`/prep-today`) - Modify today (live)
3. **Schedule Edit (Tomorrow)** (`/prep-tomorrow`) - Prepare tomorrow (staged)
4. **Weight Matrix** (`/button-weights`) - Configure button weights and special task weights

### Navigation & UI Features

**Cortex layout** - Unified navigation across all pages:
- **Dashboard** (`/`) - Main workload view (toggle Modality/Skill views)
- **Timetable** (`/timetable`) - Visual timeline of shifts and gaps
- **Skill Matrix** (`/skill-roster`) - Manage worker skills (direct save)
- **Change Today** (`/prep-today`) - Live edits for today
- **Prep Tomorrow** (`/prep-tomorrow`) - Staged edits for tomorrow
- **Worker Load** (`/worker-load`) - Load monitoring dashboard
- **Weight Matrix** (`/button-weights`) - Configure button and special task weights
- **Admin** (`/upload`) - System configuration and CSV uploads

---

## Project Structure

```
RadIMO_Cortex/
├── app.py                      # Main entry point (Flask app)
├── routes.py                   # Route and API definitions
├── balancer.py                 # Load balancing logic
├── config.py                   # Config loader and normalization
├── config.yaml                 # Configuration (mapping, skills, special tasks)
├── requirements.txt            # Python dependencies
├── gunicorn_config.py          # Gunicorn server configuration
├── data/                       # Persistent data files (auto-created)
│   ├── worker_skill_roster.json  # Worker skill roster
│   ├── button_weights.json       # Button weights for skills/special tasks
│   ├── fairness_state.json       # Application state persistence
│   └── backups/                  # Automatic backups (rotated, n=5)
│       ├── worker_skill_roster_*.json
│       ├── button_weights_*.json
│       └── fairness_state_*.json
├── uploads/                    # Runtime schedule data
│   └── backups/                # Schedule backups (staged/live/scheduled)
├── data_manager/               # Data handling and state management
│   ├── __init__.py              # Package exports
│   ├── csv_parser.py            # CSV parsing utilities
│   ├── file_ops.py              # File handling helpers
│   ├── json_manager.py          # Centralized JSON file management
│   ├── schedule_crud.py         # Schedule create/update/delete
│   ├── scheduled_tasks.py       # Scheduled jobs and timers
│   ├── state_persistence.py     # Save/load system state
│   └── worker_management.py     # Worker roster management
├── lib/                        # Library modules
│   ├── utils.py                # Utility functions and logging
│   └── usage_logger.py         # Usage tracking
├── scripts/                    # Development and utility scripts
│   ├── ops_check.py            # Pre-deployment checks
│   ├── prepare_config.py       # Config generator from CSV
│   ├── exam_values.py          # Exam value export/import tool
│   └── code_aggregator.py      # Documentation export tool
├── test_data/                  # Test CSV files and examples
├── templates/                  # HTML templates (Admin pages aligned to Prep)
├── static/                     # CSS, JS, assets
│   ├── EULA.txt                 # Licensing terms
│   └── verfahrensverzeichniss.txt # GDPR documentation (German)
└── docs/                       # Documentation
    ├── ADMIN_GUIDE.md          # Admin pages guide
    ├── API.md                  # API endpoints
    ├── CONFIGURATION.md        # Config reference (incl. special tasks)
    ├── USAGE_LOGGING.md        # Usage logging documentation
    └── WORKFLOW.md             # Master CSV workflow guide
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [WORKFLOW.md](docs/WORKFLOW.md) | Medweb CSV workflow, upload strategies |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Full config.yaml reference |
| [API.md](docs/API.md) | REST API endpoints |
| [ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | Admin pages and skill roster |

---

## Operational Checks

Run system health checks:

```bash
python scripts/ops_check.py
```

Validates: config file, admin password, upload folder, modalities, skills, medweb mapping rules.

---

## Security

- **Admin password**: Configure in `config.yaml` (enforced when `admin_access_protection_enabled` is true)
- **Access password**: Optional access login for non-admin pages (`access_protection_enabled`)
- **Session-based auth**: Admin routes protected by login when enabled
- **GDPR-compliant**: Documentation in `static/verfahrensverzeichniss.txt`

---

## Version

**RadIMO Cortex v20** - Current production version

For more information, see [EULA.txt](static/EULA.txt) or contact **Dr. M. Russe**.

---

**Made for radiology teams**
