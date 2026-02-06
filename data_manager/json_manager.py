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
from typing import Dict, Any, List, Optional, Set

# -----------------------------------------------------------
# File Path Configuration
# -----------------------------------------------------------

# Base data directory (relative to project root)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DATA_BACKUPS_DIR = os.path.join(DATA_DIR, 'backups')

# JSON file paths
WORKER_SKILL_ROSTER_PATH = os.path.join(DATA_DIR, 'worker_skill_roster.json')

# Default number of backups to keep
DEFAULT_BACKUP_COUNT = 5

# File operation lock
_file_lock = Lock()


def ensure_data_dirs() -> None:
    """Ensure all data directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DATA_BACKUPS_DIR, exist_ok=True)


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
    for worker_id, worker_data in roster_data.items():
        # Check if worker should be removed
        if remove_unknown_workers and known_worker_ids and worker_id not in known_worker_ids:
            continue

        if not isinstance(worker_data, dict):
            cleaned[worker_id] = worker_data
            continue

        cleaned_worker = {}
        for key, value in worker_data.items():
            if key in metadata_fields or key in valid_skill_modality_keys:
                cleaned_worker[key] = value

        cleaned[worker_id] = cleaned_worker

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


# Ensure directories exist on module load
ensure_data_dirs()
