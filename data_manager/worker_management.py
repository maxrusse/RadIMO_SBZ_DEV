"""
Worker management module for handling worker IDs, skill rosters, and worker data.

This module provides functions for:
- Canonical worker ID mapping
- Skill roster loading/saving (JSON)
- Worker-skill-modality combination management
- Skill roster merging (YAML + JSON)
"""
import copy
import json
from typing import Dict, Any, List

import pandas as pd

from config import (
    allowed_modalities,
    SKILL_COLUMNS,
    MODALITY_SETTINGS,
    allowed_modalities_map,
    skill_columns_map,
    SKILL_ROSTER_AUTO_IMPORT,
    selection_logger,
)
from lib.utils import is_weighted_skill
from state_manager import StateManager

# Get state references
_state = StateManager.get_instance()
global_worker_data = _state.global_worker_data
worker_skill_json_roster = _state.worker_skill_json_roster


def get_canonical_worker_id(worker_name: str) -> str:
    """Map worker name variations to a single canonical identifier."""
    worker_name = '' if worker_name is None else str(worker_name)
    worker_key = worker_name.strip()

    if worker_key in global_worker_data['worker_ids']:
        return global_worker_data['worker_ids'][worker_key]

    canonical_id = worker_key
    abk_match = worker_key.split('(')
    if len(abk_match) > 1 and ')' in abk_match[1]:
        abbreviation = abk_match[1].split(')')[0].strip()
        if abbreviation:
            canonical_id = abbreviation

    canonical_id = canonical_id or worker_key
    global_worker_data['worker_ids'][worker_key] = canonical_id
    return canonical_id


def invalidate_work_hours_cache(modality: str = None) -> None:
    """Invalidate the work hours cache when modality data changes.

    Args:
        modality: Specific modality to invalidate, or None for all modalities.
    """
    _state.invalidate_work_hours_cache(modality)


def get_all_workers_by_canonical_id():
    """Get mapping of canonical IDs to all name variations."""
    canonical_to_variations = {}
    for name, canonical in global_worker_data['worker_ids'].items():
        if canonical not in canonical_to_variations:
            canonical_to_variations[canonical] = []
        canonical_to_variations[canonical].append(name)
    return canonical_to_variations


def load_worker_skill_json() -> Dict[str, Any]:
    """Load worker skill roster from JSON file."""
    filename = 'worker_skill_roster.json'
    try:
        with open(filename, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            # Update global cache
            worker_skill_json_roster.clear()
            worker_skill_json_roster.update(data)
            selection_logger.info(f"Loaded worker skill roster: {len(data)} workers")
            return data
    except FileNotFoundError:
        selection_logger.info(f"No {filename} found, using empty roster")
        worker_skill_json_roster.clear()
        return {}
    except Exception as exc:
        selection_logger.warning(f"Failed to load {filename}: {exc}")
        return {}


def save_worker_skill_json(roster_data: Dict[str, Any]) -> bool:
    """Save worker skill roster to JSON file."""
    filename = 'worker_skill_roster.json'
    try:
        with open(filename, 'w', encoding='utf-8') as json_file:
            json.dump(roster_data, json_file, indent=2, ensure_ascii=False)
        selection_logger.info(f"Saved worker skill roster: {len(roster_data)} workers")
        return True
    except Exception as exc:
        selection_logger.error(f"Failed to save {filename}: {exc}")
        return False


def build_valid_skills_map() -> Dict[str, List[str]]:
    """Build map of valid skills per modality (for filtering in UI)."""
    valid_skills_map: Dict[str, List[str]] = {}
    for mod, settings in MODALITY_SETTINGS.items():
        if 'valid_skills' in settings:
            valid_skills_map[mod] = settings['valid_skills']
        else:
            valid_skills_map[mod] = SKILL_COLUMNS
    return valid_skills_map


def normalize_skill_mod_key(key: str) -> str:
    """
    Normalize skill_modality key to canonical format: "skill_modality".

    Accepts both "skill_modality" and "modality_skill" formats.
    Returns canonical "skill_modality" format with case-insensitive matching.

    Examples:
        "MSK_ct" -> "MSK_ct"
        "ct_MSK" -> "MSK_ct"
        "msk_CT" -> "MSK_ct"  (case-insensitive)
        "Notfall_mr" -> "Notfall_mr"
    """
    if '_' not in key:
        return key

    parts = key.split('_', 1)
    if len(parts) != 2:
        return key

    part1_lower, part2_lower = parts[0].lower(), parts[1].lower()

    # Check if part1 is a skill and part2 is a modality
    skill1 = skill_columns_map.get(part1_lower)
    mod2 = allowed_modalities_map.get(part2_lower)
    if skill1 and mod2:
        return f"{skill1}_{mod2}"  # skill_modality format

    # Check if part1 is a modality and part2 is a skill (reversed)
    mod1 = allowed_modalities_map.get(part1_lower)
    skill2 = skill_columns_map.get(part2_lower)
    if mod1 and skill2:
        return f"{skill2}_{mod1}"  # Normalize to skill_modality

    # Unknown format - return as-is
    return key


def build_disabled_worker_entry() -> Dict[str, Any]:
    """
    Create a new worker entry with all Skill x Modality combinations disabled (-1).

    Format: {"skill_modality": -1, ...} (flat structure)
    Example: {"MSK_ct": -1, "MSK_mr": -1, "Notfall_ct": -1, ...}
    """
    entry: Dict[str, Any] = {}
    for skill in SKILL_COLUMNS:
        for mod in allowed_modalities:
            key = f"{skill}_{mod}"
            entry[key] = -1
    return entry


def get_roster_modifier(canonical_id: str) -> float:
    """
    Get worker's global modifier from skill roster.

    Returns the 'modifier' field from the worker's roster entry.
    Defaults to 1.0 if not set or worker not in roster.

    Args:
        canonical_id: Worker's canonical ID

    Returns:
        Modifier value (float), defaults to 1.0
    """
    # Ensure roster is loaded
    if not worker_skill_json_roster:
        load_worker_skill_json()

    worker_data = worker_skill_json_roster.get(canonical_id, {})
    modifier = worker_data.get('modifier', 1.0)

    try:
        modifier = float(modifier)
        if modifier <= 0:
            modifier = 1.0
    except (TypeError, ValueError):
        modifier = 1.0

    return modifier


def auto_populate_skill_roster(modality_dfs: Dict[str, pd.DataFrame]) -> int:
    """
    Auto-populate skill roster with new workers found in uploaded schedules.

    New workers are added with all skills disabled (-1) by default.
    Uses canonical_id (derived from PPL if not present) to ensure consistent worker IDs.
    """
    roster = load_worker_skill_json()
    added_count = 0

    for modality, df in modality_dfs.items():
        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            # Always derive canonical_id from PPL to ensure consistent IDs
            # The canonical_id is typically the abbreviation/code extracted from "Name (Code)"
            ppl_value = row.get('PPL', '')
            if pd.isna(ppl_value) or not str(ppl_value).strip():
                continue

            # Use get_canonical_worker_id to extract consistent ID (e.g., "ABC" from "Name (ABC)")
            worker_id = get_canonical_worker_id(str(ppl_value))
            if not worker_id or worker_id in roster:
                continue

            roster[worker_id] = build_disabled_worker_entry()
            added_count += 1
            selection_logger.info(
                "Auto-added worker %s to skill roster with all skills disabled",
                worker_id,
            )

    if added_count > 0:
        save_worker_skill_json(roster)

    return added_count


def get_merged_worker_roster(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge YAML config roster with JSON roster.

    JSON roster has priority and completely overrides YAML entries for the same worker.
    Format: {worker_id: {'default': {skills}, 'ct': {overrides}, ...}}
    """
    # Start with YAML config
    yaml_roster = config.get('worker_roster', {})
    merged = copy.deepcopy(yaml_roster)

    # Ensure JSON is loaded
    if not worker_skill_json_roster:
        load_worker_skill_json()

    # JSON roster completely overrides YAML for each worker
    for worker_id, worker_data in worker_skill_json_roster.items():
        merged[worker_id] = copy.deepcopy(worker_data)

    return merged


def get_worker_skill_mod_combinations(canonical_id: str, worker_roster: dict) -> dict:
    """
    Get worker's Skill x Modality combinations from roster.

    Returns flat dict: {"skill_modality": value, ...}
    Normalizes keys to canonical "skill_modality" format.
    Missing combinations default to 0 (passive).
    """
    if canonical_id not in worker_roster:
        # Worker not in roster -> all combinations = 0 (passive)
        result = {}
        for skill in SKILL_COLUMNS:
            for mod in allowed_modalities:
                result[f"{skill}_{mod}"] = 0
        return result

    worker_data = worker_roster[canonical_id]
    result = {}

    # Initialize all combinations to 0
    for skill in SKILL_COLUMNS:
        for mod in allowed_modalities:
            result[f"{skill}_{mod}"] = 0

    # Apply roster values (normalize keys)
    for key, value in worker_data.items():
        normalized_key = normalize_skill_mod_key(key)
        if normalized_key in result:
            result[normalized_key] = value

    return result


def expand_skill_overrides(rule_overrides: dict) -> dict:
    """
    Expand skill_overrides shortcuts to full skill_modality combinations.

    Supports:
        - Full keys: "MSK_ct": 1 -> {"MSK_ct": 1}
        - all shortcut: "all": -1 -> all skill_modality combos = -1
        - Skill shortcut: "MSK": 1 -> MSK_ct, MSK_mr, MSK_xray, MSK_mammo = 1
        - Modality shortcut: "ct": 1 -> Notfall_ct, MSK_ct, Privat_ct, etc. = 1

    Args:
        rule_overrides: Raw skill_overrides dict from config

    Returns:
        Expanded dict with full skill_modality keys (canonical names)
    """
    expanded = {}

    for key, value in rule_overrides.items():
        key_lower = key.lower()

        # Check for "all" shortcut
        if key_lower == 'all':
            for skill in SKILL_COLUMNS:
                for mod in allowed_modalities:
                    expanded[f"{skill}_{mod}"] = value
            continue

        # Check if key is a skill shortcut (e.g., "MSK" or "msk")
        canonical_skill = skill_columns_map.get(key_lower)
        if canonical_skill:
            for mod in allowed_modalities:
                expanded[f"{canonical_skill}_{mod}"] = value
            continue

        # Check if key is a modality shortcut (e.g., "ct" or "CT")
        canonical_mod = allowed_modalities_map.get(key_lower)
        if canonical_mod:
            for skill in SKILL_COLUMNS:
                expanded[f"{skill}_{canonical_mod}"] = value
            continue

        # Otherwise, it's a full skill_modality key - normalize it
        normalized_key = normalize_skill_mod_key(key)
        expanded[normalized_key] = value

    return expanded


def apply_skill_overrides(roster_combinations: dict, rule_overrides: dict) -> dict:
    """
    Apply CSV rule skill_overrides to roster Skill x Modality combinations.

    First expands shortcuts (all, skill-only, mod-only), then applies.

    Priority rules:
    - Roster -1 (hard exclude) always wins and cannot be overridden
    - Roster 'w' (weighted/training):
      - CSV 1 → 'w' (worker is weighted, stays weighted)
      - CSV 0 → -1 (not assigned to team, excluded)
      - CSV -1 → -1 (explicit exclusion)
      - No override → -1 (not on any shift, excluded)
    - Roster 1 or 0 → use CSV value (normal override)

    Args:
        roster_combinations: Worker's baseline skill x modality combinations
        rule_overrides: CSV rule overrides (e.g., {"MSK_ct": 1, "all": -1})

    Returns:
        Final skill x modality combinations
    """
    final = roster_combinations.copy()

    # Expand shortcuts first
    expanded_overrides = expand_skill_overrides(rule_overrides)

    # Track which keys have been processed by an override
    processed_keys = set()

    for key, override_value in expanded_overrides.items():
        if key in final:
            processed_keys.add(key)
            roster_value = final[key]

            # Roster -1 (hard exclude) always wins
            if roster_value == -1:
                continue  # Keep -1, ignore override

            # Roster 'w' (weighted/training) special handling
            if is_weighted_skill(roster_value):
                if override_value == 1:
                    # CSV assigns as specialist → keep as weighted
                    final[key] = 'w'
                else:
                    # CSV assigns as 0 (helper) or -1 (exclude) → exclude
                    # Weighted workers are only included when explicitly assigned
                    final[key] = -1
                continue

            # Normal override for roster 1 or 0
            final[key] = override_value

    # Handle roster 'w' values that were NOT processed by any override
    # These workers are not on any shift for this skill → exclude them
    for key, value in final.items():
        if key not in processed_keys and is_weighted_skill(value):
            final[key] = -1

    return final


def extract_modalities_from_skill_overrides(skill_overrides: dict) -> List[str]:
    """
    Extract unique modalities from skill_overrides keys.

    Handles all key formats:
    - "all" → all modalities
    - Skill shortcut (e.g., "MSK") → all modalities
    - Modality shortcut (e.g., "ct") → just that modality
    - Full key (e.g., "MSK_ct") → extract modality from key

    Returns list of unique canonical modalities found.
    """
    modalities = set()

    for key in skill_overrides.keys():
        key_lower = key.lower()

        # "all" shortcut → all modalities
        if key_lower == 'all':
            return list(allowed_modalities)

        # Skill-only shortcut (e.g., "MSK") → all modalities
        if skill_columns_map.get(key_lower):
            modalities.update(allowed_modalities)
            continue

        # Modality-only shortcut (e.g., "ct") → just that modality
        canonical_mod = allowed_modalities_map.get(key_lower)
        if canonical_mod:
            modalities.add(canonical_mod)
            continue

        # Full "skill_modality" key → extract modality
        normalized = normalize_skill_mod_key(key)
        if '_' in normalized:
            parts = normalized.split('_', 1)
            if len(parts) == 2:
                mod = parts[1]
                if mod in allowed_modalities:
                    modalities.add(mod)

    return list(modalities)
