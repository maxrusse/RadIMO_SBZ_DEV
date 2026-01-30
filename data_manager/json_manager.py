"""
Centralized JSON data file management module.

This module provides:
- Centralized file paths for all JSON data files
- Automatic backup rotation (n backups on changes)
- Legacy entry cleanup methods for each JSON type
- Thread-safe file operations with atomic writes
"""
import os
import json
import shutil
import glob as glob_module
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, Any, List, Optional, Set, Callable

# -----------------------------------------------------------
# File Path Configuration
# -----------------------------------------------------------

# Base data directory (relative to project root)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DATA_BACKUPS_DIR = os.path.join(DATA_DIR, 'backups')

# JSON file paths
WORKER_SKILL_ROSTER_PATH = os.path.join(DATA_DIR, 'worker_skill_roster.json')
BUTTON_WEIGHTS_PATH = os.path.join(DATA_DIR, 'button_weights.json')
FAIRNESS_STATE_PATH = os.path.join(DATA_DIR, 'fairness_state.json')

# Schedule backup paths (still in uploads for now, can be migrated later)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
SCHEDULE_BACKUPS_DIR = os.path.join(UPLOAD_FOLDER, 'backups')

# Default number of backups to keep
DEFAULT_BACKUP_COUNT = 5

# File operation lock
_file_lock = Lock()


def ensure_data_dirs() -> None:
    """Ensure all data directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DATA_BACKUPS_DIR, exist_ok=True)
    os.makedirs(SCHEDULE_BACKUPS_DIR, exist_ok=True)


# -----------------------------------------------------------
# Backup Management
# -----------------------------------------------------------

def _get_backup_path(original_path: str, timestamp: Optional[str] = None) -> str:
    """Generate backup path for a file."""
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    path = Path(original_path)
    backup_name = f"{path.stem}_{timestamp}{path.suffix}"
    return os.path.join(DATA_BACKUPS_DIR, backup_name)


def _rotate_backups(base_name: str, max_backups: int = DEFAULT_BACKUP_COUNT) -> None:
    """
    Remove old backups, keeping only the most recent max_backups.

    Args:
        base_name: Base filename without extension (e.g., 'worker_skill_roster')
        max_backups: Maximum number of backups to keep
    """
    pattern = os.path.join(DATA_BACKUPS_DIR, f"{base_name}_*.json")
    backups = sorted(glob_module.glob(pattern), reverse=True)

    # Remove excess backups
    for backup in backups[max_backups:]:
        try:
            os.remove(backup)
        except OSError:
            pass


def create_backup(file_path: str, max_backups: int = DEFAULT_BACKUP_COUNT) -> Optional[str]:
    """
    Create a backup of a JSON file before modification.

    Args:
        file_path: Path to the file to backup
        max_backups: Maximum number of backups to keep

    Returns:
        Path to the backup file, or None if backup failed
    """
    if not os.path.exists(file_path):
        return None

    try:
        backup_path = _get_backup_path(file_path)
        shutil.copy2(file_path, backup_path)

        # Rotate old backups
        base_name = Path(file_path).stem
        _rotate_backups(base_name, max_backups)

        return backup_path
    except OSError:
        return None


def list_backups(base_name: str) -> List[Dict[str, Any]]:
    """
    List all backups for a given file.

    Args:
        base_name: Base filename without extension (e.g., 'worker_skill_roster')

    Returns:
        List of backup info dicts with 'path', 'timestamp', 'size'
    """
    pattern = os.path.join(DATA_BACKUPS_DIR, f"{base_name}_*.json")
    backups = []

    for path in sorted(glob_module.glob(pattern), reverse=True):
        try:
            stat = os.stat(path)
            # Extract timestamp from filename
            filename = Path(path).stem
            timestamp_str = filename.replace(f"{base_name}_", "")
            backups.append({
                'path': path,
                'filename': Path(path).name,
                'timestamp': timestamp_str,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            pass

    return backups


def restore_backup(backup_path: str, target_path: str) -> bool:
    """
    Restore a file from backup.

    Args:
        backup_path: Path to the backup file
        target_path: Path to restore to

    Returns:
        True if restore was successful
    """
    try:
        shutil.copy2(backup_path, target_path)
        return True
    except OSError:
        return False


# -----------------------------------------------------------
# Generic JSON File Operations
# -----------------------------------------------------------

def load_json(file_path: str, default: Any = None) -> Any:
    """
    Load JSON data from file with error handling.

    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid

    Returns:
        Parsed JSON data or default value
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except json.JSONDecodeError:
        return default if default is not None else {}


def save_json(
    file_path: str,
    data: Any,
    *,
    create_backup: bool = True,
    max_backups: int = DEFAULT_BACKUP_COUNT,
    indent: int = 2,
) -> bool:
    """
    Save JSON data to file with optional backup.

    Args:
        file_path: Path to JSON file
        data: Data to save
        create_backup: Whether to create a backup before saving
        max_backups: Maximum number of backups to keep
        indent: JSON indentation level

    Returns:
        True if save was successful
    """
    ensure_data_dirs()

    with _file_lock:
        try:
            # Create backup if file exists and backup is requested
            if create_backup and os.path.exists(file_path):
                backup_path = _get_backup_path(file_path)
                shutil.copy2(file_path, backup_path)
                base_name = Path(file_path).stem
                _rotate_backups(base_name, max_backups)

            # Write atomically using temp file
            temp_path = f"{file_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)

            # Atomic rename
            os.replace(temp_path, file_path)
            return True

        except OSError:
            # Cleanup temp file if it exists
            temp_path = f"{file_path}.tmp"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False


# -----------------------------------------------------------
# Legacy Entry Cleanup
# -----------------------------------------------------------

def cleanup_worker_skill_roster(
    roster_data: Dict[str, Any],
    valid_skill_modality_keys: Set[str],
    *,
    remove_unknown_workers: bool = False,
    known_worker_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Clean up legacy entries from worker skill roster.

    Removes:
    - Unknown skill_modality keys that don't match current config
    - Optionally removes unknown worker IDs

    Keeps:
    - 'full_name', 'modifier', 'global_modifier' metadata fields

    Args:
        roster_data: Current roster data
        valid_skill_modality_keys: Set of valid 'skill_modality' keys
        remove_unknown_workers: If True, remove workers not in known_worker_ids
        known_worker_ids: Set of valid worker IDs (required if remove_unknown_workers=True)

    Returns:
        Cleaned roster data
    """
    # Metadata fields to preserve
    metadata_fields = {'full_name', 'modifier', 'global_modifier'}

    cleaned = {}
    removed_keys = []
    removed_workers = []

    for worker_id, worker_data in roster_data.items():
        # Check if worker should be removed
        if remove_unknown_workers and known_worker_ids and worker_id not in known_worker_ids:
            removed_workers.append(worker_id)
            continue

        if not isinstance(worker_data, dict):
            cleaned[worker_id] = worker_data
            continue

        cleaned_worker = {}
        for key, value in worker_data.items():
            # Keep metadata fields
            if key in metadata_fields:
                cleaned_worker[key] = value
                continue

            # Check if this is a valid skill_modality key
            if key in valid_skill_modality_keys:
                cleaned_worker[key] = value
            else:
                removed_keys.append(f"{worker_id}.{key}")

        cleaned[worker_id] = cleaned_worker

    return cleaned


def cleanup_button_weights(
    weights_data: Dict[str, Any],
    valid_skill_modality_keys: Set[str],
    valid_special_task_keys: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Clean up legacy entries from button weights.

    Removes:
    - Unknown skill_modality keys in 'normal' and 'strict' sections
    - Unknown special task keys in 'special.normal' and 'special.strict' sections

    Args:
        weights_data: Current weights data
        valid_skill_modality_keys: Set of valid 'skill_modality' keys
        valid_special_task_keys: Set of valid special task modality keys (e.g., 'task-slug_ct')

    Returns:
        Cleaned weights data
    """
    if valid_special_task_keys is None:
        valid_special_task_keys = set()

    cleaned = {
        'normal': {},
        'strict': {},
        'special': {'normal': {}, 'strict': {}},
    }

    # Clean normal weights
    for key, value in weights_data.get('normal', {}).items():
        if key in valid_skill_modality_keys:
            cleaned['normal'][key] = value

    # Clean strict weights
    for key, value in weights_data.get('strict', {}).items():
        if key in valid_skill_modality_keys:
            cleaned['strict'][key] = value

    # Clean special task weights
    special_weights = weights_data.get('special', {})
    if isinstance(special_weights, dict):
        for key, value in special_weights.get('normal', {}).items():
            if key in valid_special_task_keys:
                cleaned['special']['normal'][key] = value

        for key, value in special_weights.get('strict', {}).items():
            if key in valid_special_task_keys:
                cleaned['special']['strict'][key] = value

    return cleaned


def cleanup_fairness_state(
    state_data: Dict[str, Any],
    valid_modalities: Set[str],
    valid_skill_columns: Set[str],
) -> Dict[str, Any]:
    """
    Clean up legacy entries from fairness state.

    Removes:
    - Unknown modalities from assignments_per_mod and modality_data
    - Unknown skills from skill_counts

    Args:
        state_data: Current state data
        valid_modalities: Set of valid modality codes
        valid_skill_columns: Set of valid skill column names

    Returns:
        Cleaned state data
    """
    cleaned = {}

    # Clean global_worker_data
    if 'global_worker_data' in state_data:
        gwd = state_data['global_worker_data']
        cleaned_gwd = {
            'worker_ids': gwd.get('worker_ids', {}),
            'weighted_counts': gwd.get('weighted_counts', {}),
            'assignments_per_mod': {},
            'last_reset_date': gwd.get('last_reset_date'),
        }

        # Only keep valid modalities in assignments_per_mod
        for mod, data in gwd.get('assignments_per_mod', {}).items():
            if mod in valid_modalities:
                cleaned_gwd['assignments_per_mod'][mod] = data

        cleaned['global_worker_data'] = cleaned_gwd

    # Clean modality_data
    if 'modality_data' in state_data:
        cleaned_md = {}
        for mod, mod_data in state_data['modality_data'].items():
            if mod not in valid_modalities:
                continue

            cleaned_mod = {
                'last_reset_date': mod_data.get('last_reset_date'),
                'skill_counts': {},
            }

            # Only keep valid skills in skill_counts
            for skill, counts in mod_data.get('skill_counts', {}).items():
                if skill in valid_skill_columns:
                    cleaned_mod['skill_counts'][skill] = counts

            cleaned_md[mod] = cleaned_mod

        cleaned['modality_data'] = cleaned_md

    return cleaned


# -----------------------------------------------------------
# Migration Helpers
# -----------------------------------------------------------

def migrate_file_to_data_dir(old_path: str, new_path: str) -> bool:
    """
    Migrate a file from old location to new data directory.

    Args:
        old_path: Current file path
        new_path: New path in data directory

    Returns:
        True if migration was successful or file didn't exist
    """
    if not os.path.exists(old_path):
        return True

    ensure_data_dirs()

    try:
        # Don't overwrite if new file already exists
        if os.path.exists(new_path):
            # Keep the newer file
            old_mtime = os.path.getmtime(old_path)
            new_mtime = os.path.getmtime(new_path)
            if old_mtime > new_mtime:
                shutil.copy2(old_path, new_path)
        else:
            shutil.copy2(old_path, new_path)

        # Remove old file after successful copy
        os.remove(old_path)
        return True
    except OSError:
        return False


def migrate_all_json_files() -> Dict[str, bool]:
    """
    Migrate all JSON files to the new data directory structure.

    Returns:
        Dict mapping file names to migration success status
    """
    migrations = {
        'worker_skill_roster.json': (
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'worker_skill_roster.json'),
            WORKER_SKILL_ROSTER_PATH,
        ),
        'button_weights.json': (
            os.path.join(UPLOAD_FOLDER, 'button_weights.json'),
            BUTTON_WEIGHTS_PATH,
        ),
        'fairness_state.json': (
            os.path.join(UPLOAD_FOLDER, 'fairness_state.json'),
            FAIRNESS_STATE_PATH,
        ),
    }

    results = {}
    for name, (old_path, new_path) in migrations.items():
        results[name] = migrate_file_to_data_dir(old_path, new_path)

    return results


# Ensure directories exist on module load
ensure_data_dirs()
