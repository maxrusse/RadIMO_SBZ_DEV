# Standard library imports
import os
import json
import re
import yaml
import copy
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, List, Tuple, Optional
from lib.utils import (
    coerce_float,
    coerce_int,
    selection_logger
)

# -----------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

MASTER_CSV_PATH = os.path.join(UPLOAD_FOLDER, 'master_medweb.csv')
STATE_FILE_PATH = os.path.join(UPLOAD_FOLDER, 'fairness_state.json')
BUTTON_WEIGHTS_PATH = os.path.join(UPLOAD_FOLDER, 'button_weights.json')

os.makedirs('logs', exist_ok=True)
selection_logger.setLevel(logging.INFO)

# Avoid adding multiple handlers if reloaded
if not selection_logger.handlers:
    handler = RotatingFileHandler('logs/selection.log', maxBytes=10_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    selection_logger.addHandler(handler)

# -----------------------------------------------------------
# Default Constants
# -----------------------------------------------------------
DEFAULT_ADMIN_PASSWORD = 'change_pw_for_live'
DEFAULT_ACCESS_PASSWORD = 'change_easy_pw'  # Basic access password for non-admin pages
DEFAULT_ACCESS_PROTECTION_ENABLED = False
DEFAULT_ADMIN_ACCESS_PROTECTION_ENABLED = False
DEFAULT_SECRET_KEY = 'super_secret_key_for_dev'  # Change this in production
DEFAULT_TIMEZONE = 'Europe/Berlin'  # Default timezone for all date/time operations

DEFAULT_BALANCER = {
    'enabled': True,
    'min_assignments_per_skill': 3,
    'imbalance_threshold_pct': 30,
    'disable_overflow_at_shift_start_minutes': 0,  # 0 = disabled
    'disable_overflow_at_shift_end_minutes': 0,  # 0 = disabled
    'default_w_modifier': 0.5,
}

# -----------------------------------------------------------
# Config Loading Logic
# -----------------------------------------------------------
def _load_raw_config() -> Dict[str, Any]:
    try:
        with open('config.yaml', 'r', encoding='utf-8') as config_file:
            return yaml.safe_load(config_file) or {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        selection_logger.warning("Failed to load config.yaml: %s", exc)
        return {}

def _validate_name(name: str, name_type: str) -> None:
    """Warn if a modality or skill name contains problematic characters.

    Underscores and spaces in names would break the skill_modality key format
    (e.g., 'MSK_ct') which uses '_' as the separator.
    """
    if '_' in name:
        selection_logger.warning(
            "%s name '%s' contains underscore - this will break skill_modality key parsing. "
            "Please rename to remove underscores.", name_type, name
        )
    if ' ' in name:
        selection_logger.warning(
            "%s name '%s' contains space - this may cause inconsistencies. "
            "Consider removing spaces.", name_type, name
        )


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower())
    return slug.strip('-')


def _build_app_config() -> Dict[str, Any]:
    raw_config = _load_raw_config()
    config: Dict[str, Any] = {
        'admin_password': raw_config.get('admin_password', DEFAULT_ADMIN_PASSWORD),
        'access_password': raw_config.get('access_password', DEFAULT_ACCESS_PASSWORD),
        'access_protection_enabled': raw_config.get(
            'access_protection_enabled',
            DEFAULT_ACCESS_PROTECTION_ENABLED
        ),
        'admin_access_protection_enabled': raw_config.get(
            'admin_access_protection_enabled',
            DEFAULT_ADMIN_ACCESS_PROTECTION_ENABLED
        ),
        'secret_key': raw_config.get('secret_key', DEFAULT_SECRET_KEY),
        'timezone': raw_config.get('timezone', DEFAULT_TIMEZONE),
    }

    # Load modalities directly from config.yaml (no hardcoded defaults)
    merged_modalities: Dict[str, Dict[str, Any]] = {}
    user_modalities = raw_config.get('modalities') or {}
    if isinstance(user_modalities, dict):
        for key, mod_data in user_modalities.items():
            _validate_name(key, "Modality")
            if isinstance(mod_data, dict):
                merged_modalities[key] = dict(mod_data)

    # Set sensible defaults for any missing modality properties
    for key, values in merged_modalities.items():
        values.setdefault('label', key.upper())
        values.setdefault('nav_color', '#004892')
        values.setdefault('hover_color', values['nav_color'])
        values.setdefault('background_color', '#f0f0f0')

    config['modalities'] = merged_modalities

    # Load skills directly from config.yaml (no hardcoded defaults)
    merged_skills: Dict[str, Dict[str, Any]] = {}
    user_skills = raw_config.get('skills') or {}
    if isinstance(user_skills, dict):
        for key, skill_data in user_skills.items():
            _validate_name(key, "Skill")
            if isinstance(skill_data, dict):
                merged_skills[key] = dict(skill_data)

    # Set sensible defaults for any missing properties
    for key, values in merged_skills.items():
        values.setdefault('label', key)
        values.setdefault('button_color', '#004892')
        values.setdefault('text_color', '#ffffff')
        values.setdefault('special', False)
        values['display_order'] = coerce_int(values.get('display_order', 0))
        slug = values.get('slug') or _slugify(key)
        values['slug'] = slug

    config['skills'] = merged_skills

    balancer_settings: Dict[str, Any] = copy.deepcopy(DEFAULT_BALANCER)
    user_balancer = raw_config.get('balancer')
    if isinstance(user_balancer, dict):
        for key, value in user_balancer.items():
            balancer_settings[key] = value
    config['balancer'] = balancer_settings

    # Include vendor_mappings
    vendor_configs = raw_config.get('vendor_mappings', {})
    config['vendor_mappings'] = vendor_configs

    # Extract medweb mapping from vendor_mappings (required)
    config['medweb_mapping'] = vendor_configs.get('medweb', {})

    # Include worker_roster
    config['worker_roster'] = raw_config.get('worker_roster', {})

    # Include UI colors (needed for prep page)
    config['ui_colors'] = raw_config.get('ui_colors', {})
    config['skill_value_colors'] = raw_config.get('skill_value_colors', {})

    # Scheduler settings
    config['scheduler'] = raw_config.get('scheduler', {
        'daily_reset_time': '07:30',
        'auto_preload_time': 14
    })

    # Auto-import toggle for worker skill roster
    config['skill_roster_auto_import'] = bool(
        raw_config.get('skill_roster_auto_import', True)
    )

    # Worker load monitor settings
    default_load_monitor = {
        'color_thresholds': {
            'mode': 'absolute',
            'absolute': {'low': 3.0, 'high': 7.0},
            'relative': {'low_pct': 33, 'high_pct': 66}
        },
        'default_view': 'simple'
    }
    user_load_monitor = raw_config.get('worker_load_monitor', {})
    if isinstance(user_load_monitor, dict):
        # Merge with defaults
        load_monitor_config = default_load_monitor.copy()
        if 'color_thresholds' in user_load_monitor:
            load_monitor_config['color_thresholds'] = {
                **default_load_monitor['color_thresholds'],
                **user_load_monitor['color_thresholds']
            }
        if 'default_view' in user_load_monitor:
            load_monitor_config['default_view'] = user_load_monitor['default_view']
    else:
        load_monitor_config = default_load_monitor
    config['worker_load_monitor'] = load_monitor_config
    config['special_tasks'] = raw_config.get('special_tasks', [])

    return config

def _build_skill_metadata(skills_config: Dict[str, Dict[str, Any]]) -> Tuple[List[str], Dict[str, str], List[Dict[str, Any]]]:
    ordered_skills = sorted(
        skills_config.items(),
        key=lambda item: (coerce_int(item[1].get('display_order', 0)), item[0])
    )

    columns: List[str] = []
    slug_map: Dict[str, str] = {}
    templates: List[Dict[str, Any]] = []
    for name, data in ordered_skills:
        slug = data.get('slug') or _slugify(name)

        columns.append(name)
        slug_map[name] = slug

        templates.append({
            'name': name,
            'label': data.get('label', name),
            'slug': slug,
            'button_color': data.get('button_color', '#004892'),
            'text_color': data.get('text_color', '#ffffff'),
            'special': bool(data.get('special', False)),
        })

    return columns, slug_map, templates

# -----------------------------------------------------------
# Global Configuration Objects
# -----------------------------------------------------------
APP_CONFIG = _build_app_config()
MODALITY_SETTINGS = APP_CONFIG['modalities']
SKILL_SETTINGS = APP_CONFIG['skills']
SKILL_ROSTER_AUTO_IMPORT = APP_CONFIG.get('skill_roster_auto_import', True)
TIMEZONE = APP_CONFIG.get('timezone', DEFAULT_TIMEZONE)

allowed_modalities = list(MODALITY_SETTINGS.keys())
allowed_modalities_map = {m.lower(): m for m in allowed_modalities}
default_modality = allowed_modalities[0] if allowed_modalities else 'ct'
modality_labels = {
    mod: settings.get('label', mod.upper())
    for mod, settings in MODALITY_SETTINGS.items()
}
# Load no_overflow combinations (strict mode - no overflow to generalists)
_raw_no_overflow = APP_CONFIG.get('no_overflow', [])

# Build skill metadata
SKILL_COLUMNS, SKILL_SLUG_MAP, SKILL_TEMPLATES = _build_skill_metadata(SKILL_SETTINGS)
SKILL_LABEL_MAP = {
    data.get('label', name).lower(): name
    for name, data in SKILL_SETTINGS.items()
}

# Build case-insensitive lookup maps for skills
# - ROLE_MAP: slug.lower() -> canonical name (for URL/API role lookups)
# - skill_columns_map: name.lower() -> canonical name (for case-insensitive name lookups)
ROLE_MAP = {slug.lower(): name for name, slug in SKILL_SLUG_MAP.items()}
skill_columns_map = {s.lower(): s for s in SKILL_COLUMNS}

def _resolve_skill(key_lower: str) -> Optional[str]:
    """Resolve a lowercase skill key to its canonical name via slug or direct match."""
    return ROLE_MAP.get(key_lower) or SKILL_LABEL_MAP.get(key_lower) or skill_columns_map.get(key_lower)


def _normalize_special_tasks(raw_tasks: Any) -> List[Dict[str, Any]]:
    if not raw_tasks:
        return []
    if not isinstance(raw_tasks, list):
        selection_logger.warning("special_tasks must be a list of task objects")
        return []

    normalized: List[Dict[str, Any]] = []
    seen_slugs = set()

    for entry in raw_tasks:
        if not isinstance(entry, dict):
            selection_logger.warning("Skipping special task entry (expected object): %s", entry)
            continue

        name = str(entry.get('name', '')).strip()
        if not name:
            selection_logger.warning("Skipping special task without a name: %s", entry)
            continue

        slug = _slugify(name)
        if not slug:
            selection_logger.warning("Skipping special task with invalid name: %s", name)
            continue
        if slug in seen_slugs:
            selection_logger.warning("Duplicate special task name '%s' (slug '%s')", name, slug)
            continue

        base_skill_raw = entry.get('base_skill')
        if not base_skill_raw:
            selection_logger.warning("Special task '%s' missing base_skill", name)
            continue
        base_skill = _resolve_skill(str(base_skill_raw).strip().lower())
        if not base_skill:
            selection_logger.warning(
                "Special task '%s' base_skill '%s' is not a known skill", name, base_skill_raw
            )
            continue

        label = str(entry.get('label') or name)
        display_order = coerce_int(entry.get('display_order', 999))
        work_amount = coerce_float(entry.get('work_amount', 1.0), 1.0)
        if work_amount <= 0:
            selection_logger.warning(
                "Special task '%s' has invalid work_amount %s; using 1.0", name, work_amount
            )
            work_amount = 1.0
        allow_overflow = bool(entry.get('allow_overflow', True))

        raw_modalities = entry.get('modalities_dashboards', [])
        if isinstance(raw_modalities, str):
            raw_modalities = [raw_modalities]
        modalities_dashboards: List[str] = []
        if isinstance(raw_modalities, list):
            for mod in raw_modalities:
                if not isinstance(mod, str):
                    continue
                canonical_mod = allowed_modalities_map.get(mod.strip().lower())
                if canonical_mod and canonical_mod not in modalities_dashboards:
                    modalities_dashboards.append(canonical_mod)
        else:
            selection_logger.warning(
                "Special task '%s' modalities_dashboards must be a list", name
            )

        raw_skill_dashboards = entry.get('skill_dashboards', [])
        if isinstance(raw_skill_dashboards, str):
            raw_skill_dashboards = [raw_skill_dashboards]
        skill_dashboards: List[str] = []
        if isinstance(raw_skill_dashboards, list):
            for skill in raw_skill_dashboards:
                if not isinstance(skill, str):
                    continue
                canonical_skill = _resolve_skill(skill.strip().lower())
                if canonical_skill and canonical_skill not in skill_dashboards:
                    skill_dashboards.append(canonical_skill)
        else:
            selection_logger.warning(
                "Special task '%s' skill_dashboards must be a list", name
            )

        skill_config = SKILL_SETTINGS.get(base_skill, {})
        normalized.append({
            'name': name,
            'slug': slug,
            'label': label,
            'base_skill': base_skill,
            'modalities_dashboards': modalities_dashboards,
            'skill_dashboards': skill_dashboards,
            'work_amount': work_amount,
            'allow_overflow': allow_overflow,
            'display_order': display_order,
            'button_color': skill_config.get('button_color', '#004892'),
            'text_color': skill_config.get('text_color', '#ffffff'),
        })
        seen_slugs.add(slug)

    return sorted(normalized, key=lambda task: (task['display_order'], task['name']))


SPECIAL_TASKS = _normalize_special_tasks(APP_CONFIG.get('special_tasks', []))
SPECIAL_TASKS_MAP = {task['slug']: task for task in SPECIAL_TASKS}
APP_CONFIG['special_tasks'] = SPECIAL_TASKS


def _resolve_skill_modality_pair(key: str) -> Optional[Tuple[str, str]]:
    """
    Resolve a skill_modality key to canonical (skill, modality) tuple.

    Tries both orderings: skill_mod and mod_skill.
    Returns None if the key cannot be resolved.
    """
    key_lower = key.lower().strip()
    if '_' not in key_lower:
        return None

    parts = key_lower.split('_', 1)
    if len(parts) != 2:
        return None

    # Try skill_mod first
    skill = _resolve_skill(parts[0])
    mod = allowed_modalities_map.get(parts[1])

    # Try mod_skill if first attempt failed
    if not (skill and mod):
        skill = _resolve_skill(parts[1])
        mod = allowed_modalities_map.get(parts[0])

    if skill and mod:
        return (skill, mod)
    return None


def _resolve_special_task_modality_pair(key: str) -> Optional[Tuple[str, str]]:
    """
    Resolve a special_task_modality key to canonical (task_slug, modality) tuple.

    Returns None if the key cannot be resolved.
    """
    key_lower = key.lower().strip()
    if '_' not in key_lower:
        return None

    parts = key_lower.split('_', 1)
    if len(parts) != 2:
        return None

    task_slug = parts[0]
    modality = allowed_modalities_map.get(parts[1])
    if task_slug in SPECIAL_TASKS_MAP and modality:
        return (task_slug, modality)
    return None


def _normalize_exclude_skills(raw_exclude_skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Normalize exclude_skills shortcuts to canonical skill names.

    Supports:
    - Skill only: msk → MSK (all MSK_* combinations)
    - Modality only: ct → all *_ct combinations
    - skill_mod: msk_ct → MSK_ct
    - mod_skill: ct_msk → MSK_ct

    Returns: {canonical_skill_name: [canonical_excluded_skills]}
    """
    result = {}

    for key, exclude_list in raw_exclude_skills.items():
        if not isinstance(exclude_list, list):
            continue

        key_lower = key.lower().strip()
        canonical_keys = []

        pair = _resolve_skill_modality_pair(key)
        if pair:
            canonical_keys.append(f"{pair[0]}_{pair[1]}")
        elif _resolve_skill(key_lower):
            # Skill only - expand to all modalities
            canonical_skill = _resolve_skill(key_lower)
            canonical_keys = [f"{canonical_skill}_{mod}" for mod in allowed_modalities]
        elif key_lower in allowed_modalities_map:
            # Modality only - expand to all skills
            canonical_mod = allowed_modalities_map[key_lower]
            canonical_keys = [f"{skill}_{canonical_mod}" for skill in SKILL_COLUMNS]

        # Normalize the exclude list
        normalized_excludes = []
        for exclude_item in exclude_list:
            if isinstance(exclude_item, str):
                canonical = _resolve_skill(exclude_item.lower().strip())
                if canonical:
                    normalized_excludes.append(canonical)

        # Add to result (deduplicate)
        for canonical_key in canonical_keys:
            if canonical_key not in result:
                result[canonical_key] = []
            result[canonical_key].extend(normalized_excludes)
            result[canonical_key] = list(set(result[canonical_key]))

    return result


BALANCER_SETTINGS = APP_CONFIG.get('balancer', DEFAULT_BALANCER)

# Normalize exclude_skills from balancer config
raw_exclude_skills = BALANCER_SETTINGS.get('exclude_skills', {})
EXCLUDE_SKILLS = _normalize_exclude_skills(raw_exclude_skills)


def _normalize_no_overflow(raw_list: list) -> set:
    """
    Normalize no_overflow list to canonical Skill_Modality format.

    Supports:
    - Skill_Modality: card-thor_ct → card-thor_ct
    - Modality_Skill: ct_card-thor → card-thor_ct

    Returns: set of canonical 'Skill_modality' strings
    """
    result = set()

    for item in raw_list:
        if not isinstance(item, str):
            continue
        pair = _resolve_skill_modality_pair(item)
        if pair:
            result.add(f"{pair[0]}_{pair[1]}")

    return result


# Normalize per-button weights
def _normalize_button_weights(raw_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize per-button weights to canonical Skill_Modality keys.

    Supports:
    - Skill_Modality: card-thor_ct → card-thor_ct
    - Modality_Skill: ct_card-thor → card-thor_ct

    Returns: dict with "normal" and "strict" maps of canonical keys to weights
    """
    result: Dict[str, Any] = {
        'normal': {},
        'strict': {},
        'special': {'normal': {}, 'strict': {}},
    }

    if not isinstance(raw_map, dict):
        return result

    for mode in ('normal', 'strict'):
        mode_map = raw_map.get(mode, {})
        if not isinstance(mode_map, dict):
            continue
        for key, value in mode_map.items():
            if not isinstance(key, str):
                continue
            pair = _resolve_skill_modality_pair(key)
            if not pair:
                continue
            weight = coerce_float(value, 1.0)
            result[mode][f"{pair[0]}_{pair[1]}"] = weight

    special_map = raw_map.get('special', {})
    if isinstance(special_map, dict):
        for mode in ('normal', 'strict'):
            mode_map = special_map.get(mode, {})
            if not isinstance(mode_map, dict):
                continue
            for key, value in mode_map.items():
                if not isinstance(key, str):
                    continue
                pair = _resolve_special_task_modality_pair(key)
                if not pair:
                    continue
                weight = coerce_float(value, 1.0)
                result['special'][mode][f"{pair[0]}_{pair[1]}"] = weight

    return result


# Normalize no_overflow list
NO_OVERFLOW = _normalize_no_overflow(_raw_no_overflow)

def load_button_weights() -> Dict[str, Any]:
    try:
        with open(BUTTON_WEIGHTS_PATH, 'r', encoding='utf-8') as weight_file:
            data = json.load(weight_file)
    except FileNotFoundError:
        return _normalize_button_weights({})
    except Exception as exc:
        selection_logger.warning("Failed to load button weights: %s", exc)
        return _normalize_button_weights({})
    return _normalize_button_weights(data)

def save_button_weights(raw_weights: Dict[str, Any]) -> bool:
    normalized = _normalize_button_weights(raw_weights or {})
    try:
        with open(BUTTON_WEIGHTS_PATH, 'w', encoding='utf-8') as weight_file:
            json.dump(normalized, weight_file, indent=2, ensure_ascii=False)
        selection_logger.info("Saved button weights")
        global BUTTON_WEIGHTS
        BUTTON_WEIGHTS = normalized
        return True
    except Exception as exc:
        selection_logger.warning("Failed to save button weights: %s", exc)
        return False

BUTTON_WEIGHTS = load_button_weights()

# -----------------------------------------------------------
# Helper functions
# -----------------------------------------------------------
def get_skill_modality_weight(skill: str, modality: str, strict: bool = False) -> float:
    """
    Get the weight for a skillxmodality combination.
    """
    key = f"{skill}_{modality}"
    base_weight = BUTTON_WEIGHTS.get('normal', {}).get(key, 1.0)
    if strict:
        strict_weight = BUTTON_WEIGHTS.get('strict', {}).get(key)
        if strict_weight is not None:
            return strict_weight
    return base_weight


def get_special_task_weight(task_slug: str, modality: str, strict: bool = False) -> float:
    key = f"{task_slug}_{modality}"
    special_weights = BUTTON_WEIGHTS.get('special', {})
    base_weight = special_weights.get('normal', {}).get(key, 1.0)
    if strict:
        strict_weight = special_weights.get('strict', {}).get(key)
        if strict_weight is not None:
            return strict_weight
    return base_weight


def normalize_modality(modality_value: Optional[str]) -> str:
    if not modality_value:
        return default_modality
    modality_value_lower = modality_value.lower()
    return allowed_modalities_map.get(modality_value_lower, default_modality)


def normalize_skill(skill_name: Optional[str]) -> str:
    if not skill_name:
        return SKILL_COLUMNS[0] if SKILL_COLUMNS else ''
    key = skill_name.lower().strip()
    return _resolve_skill(key) or skill_name.strip()


def is_no_overflow(skill: str, modality: str) -> bool:
    """
    Check if a skill×modality combination has overflow disabled.

    When True, the normal button acts like the [*] strict button -
    only specialists will be assigned, never generalists.
    """
    key = f"{skill}_{modality}"
    return key in NO_OVERFLOW
