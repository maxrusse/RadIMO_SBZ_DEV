# state_manager.py
"""
Centralized state management for RadIMO Cortex.

This module provides a thread-safe Singleton class to manage all global mutable state,
replacing the previous scattered global variables (global_worker_data, modality_data,
staged_modality_data).

Benefits:
- Single source of truth for application state
- Thread-safe access via internal locking
- Easier testing through reset() method
- Supports TTL caching for expensive calculations
"""

import os
import json
import time as time_module
from threading import Lock, RLock
from typing import Dict, Any, Optional, Callable
from datetime import datetime, date
from functools import wraps


class TTLCache:
    """Simple TTL cache for expensive calculations."""

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time_module.time() - timestamp < self.ttl:
                    return value
                # Expired, remove it
                del self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        with self._lock:
            self._cache[key] = (value, time_module.time())

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate specific key or all keys if key is None."""
        with self._lock:
            if key is None:
                self._cache.clear()
            elif key in self._cache:
                del self._cache[key]

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all keys starting with prefix."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]


class StateManager:
    """
    Singleton class managing all application state.

    Thread-safe access to:
    - global_worker_data: Cross-modality worker tracking
    - modality_data: Live modality schedules and counters
    - staged_modality_data: Next-day prep data
    - worker_skill_json_roster: JSON skill roster cache

    Usage:
        state = StateManager.get_instance()
        state.global_worker_data['weighted_counts']['worker1'] = 1.5
    """

    _instance: Optional['StateManager'] = None
    _instance_lock = Lock()

    def __init__(self):
        """Initialize state structures. Use get_instance() instead of direct init."""
        # Main lock for state modifications
        self._lock = RLock()

        # TTL cache for work hours calculation (1 minute default)
        self.work_hours_cache = TTLCache(ttl_seconds=60.0)

        # Initialize empty state - will be populated by initialize()
        self._global_worker_data: Dict[str, Any] = {}
        self._modality_data: Dict[str, Dict[str, Any]] = {}
        self._staged_modality_data: Dict[str, Dict[str, Any]] = {}
        self._worker_skill_json_roster: Dict[str, Any] = {}

        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'StateManager':
        """Get the singleton instance, creating it if necessary."""
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance._initialized = False
            cls._instance = None

    def initialize(self, allowed_modalities: list, skill_columns: list, upload_folder: str) -> None:
        """
        Initialize state structures with configuration.

        Args:
            allowed_modalities: List of valid modality codes (e.g., ['ct', 'mr'])
            skill_columns: List of skill column names
            upload_folder: Base path for file storage
        """
        with self._lock:
            if self._initialized:
                return

            # Global worker data structure
            self._global_worker_data = {
                'worker_ids': {},  # Map of worker name variations to canonical ID
                'weighted_counts': {},  # {worker_id: count}
                'assignments_per_mod': {mod: {} for mod in allowed_modalities},
                'last_reset_date': None,  # Global reset date tracker
                'last_preload_date': None  # Next-workday preload tracker
            }

            # Modality active data (Live)
            self._modality_data = {}
            for mod in allowed_modalities:
                self._modality_data[mod] = {
                    'working_hours_df': None,
                    'info_texts': [],
                    'total_work_hours': {},
                    'worker_modifiers': {},
                    'skill_counts': {skill: {} for skill in skill_columns},
                    'last_reset_date': None
                }

            self._unified_schedule_paths = {
                'scheduled': os.path.join(upload_folder, "Cortex_ALL_scheduled.json"),
                'staged': os.path.join(upload_folder, "backups", "Cortex_ALL_staged.json"),
                'live': os.path.join(upload_folder, "backups", "Cortex_ALL_live.json"),
                'scheduled_backup': os.path.join(upload_folder, "backups", "Cortex_ALL_scheduled.json"),
            }

            # Staged data (Next Day Prep)
            self._staged_modality_data = {}
            for mod in allowed_modalities:
                self._staged_modality_data[mod] = {
                    'working_hours_df': None,
                    'info_texts': [],
                    'total_work_hours': {},
                    'worker_modifiers': {},
                    'last_modified': None,
                    'last_prepped_at': None,
                    'last_prepped_by': None,
                    'target_date': None
                }

            self._worker_skill_json_roster = {}
            self._initialized = True

    @property
    def lock(self) -> RLock:
        """Access the state lock for atomic operations."""
        return self._lock

    @property
    def global_worker_data(self) -> Dict[str, Any]:
        """Access global worker data dictionary."""
        return self._global_worker_data

    @property
    def modality_data(self) -> Dict[str, Dict[str, Any]]:
        """Access modality data dictionary."""
        return self._modality_data

    @property
    def staged_modality_data(self) -> Dict[str, Dict[str, Any]]:
        """Access staged modality data dictionary."""
        return self._staged_modality_data

    @property
    def worker_skill_json_roster(self) -> Dict[str, Any]:
        """Access worker skill JSON roster."""
        return self._worker_skill_json_roster

    @property
    def unified_schedule_paths(self) -> Dict[str, str]:
        """Access unified schedule file paths."""
        return self._unified_schedule_paths

    # NOTE: get_canonical_worker_id is intentionally NOT implemented here.
    # Use data_manager.worker_management.get_canonical_worker_id() instead
    # to maintain a single source of truth.

    def get_global_weighted_count(self, canonical_id: str) -> float:
        """Get single global weighted count for a worker."""
        return self._global_worker_data['weighted_counts'].get(canonical_id, 0.0)

    def invalidate_work_hours_cache(self, modality: Optional[str] = None) -> None:
        """Invalidate work hours cache for a modality or all modalities."""
        if modality:
            self.work_hours_cache.invalidate_prefix(f"work_hours:{modality}:")
        else:
            self.work_hours_cache.invalidate()

    def save_state(self, state_file_path: str, allowed_modalities: list, logger, *, create_backup: bool = True) -> None:
        """Persist state to disk with optional backup."""
        try:
            state = {
                'global_worker_data': {
                    'worker_ids': self._global_worker_data['worker_ids'],
                    'weighted_counts': self._global_worker_data['weighted_counts'],
                    'assignments_per_mod': self._global_worker_data['assignments_per_mod'],
                    'last_reset_date': self._global_worker_data['last_reset_date'].isoformat()
                        if self._global_worker_data['last_reset_date'] else None
                },
                'modality_data': {}
            }

            for mod in allowed_modalities:
                d = self._modality_data[mod]
                state['modality_data'][mod] = {
                    'skill_counts': d['skill_counts'],
                    'last_reset_date': d['last_reset_date'].isoformat() if d['last_reset_date'] else None
                }

            # Create backup before saving
            if create_backup and os.path.exists(state_file_path):
                import shutil
                backup_dir = os.path.join(os.path.dirname(state_file_path), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(backup_dir, f'fairness_state_{timestamp}.json')
                shutil.copy2(state_file_path, backup_path)
                # Rotate old backups (keep last 5)
                self._rotate_state_backups(backup_dir, max_backups=5)

            with open(state_file_path, 'w') as f:
                json.dump(state, f, indent=2)

            logger.debug("State saved successfully")
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}", exc_info=True)

    def _rotate_state_backups(self, backup_dir: str, max_backups: int = 5) -> None:
        """Remove old state backups, keeping only the most recent max_backups."""
        import glob as glob_module
        pattern = os.path.join(backup_dir, 'fairness_state_*.json')
        backups = sorted(glob_module.glob(pattern), reverse=True)
        for backup in backups[max_backups:]:
            try:
                os.remove(backup)
            except OSError:
                pass

    def load_state(self, state_file_path: str, allowed_modalities: list, skill_columns: list, logger) -> None:
        """Load state from disk with migration from old location if needed."""
        # Migrate from old location (uploads/fairness_state.json) if needed
        old_path = os.path.join('uploads', 'fairness_state.json')
        if os.path.exists(old_path) and not os.path.exists(state_file_path):
            import shutil
            try:
                os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
                shutil.copy2(old_path, state_file_path)
                os.remove(old_path)
                logger.info("Migrated fairness_state.json to data/ folder")
            except OSError as exc:
                logger.warning(f"Failed to migrate fairness_state.json: {exc}")

        try:
            with open(state_file_path, 'r') as f:
                state = json.load(f)
        except FileNotFoundError:
            logger.info("No saved state found, starting fresh")
            return
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state file: {e}")
            return

        try:
            if 'global_worker_data' in state:
                gwd = state['global_worker_data']
                self._global_worker_data['worker_ids'] = gwd.get('worker_ids', {})
                self._global_worker_data['weighted_counts'] = gwd.get('weighted_counts', {})
                self._global_worker_data['assignments_per_mod'] = gwd.get(
                    'assignments_per_mod', {mod: {} for mod in allowed_modalities}
                )

                last_reset_str = gwd.get('last_reset_date')
                if last_reset_str:
                    self._global_worker_data['last_reset_date'] = datetime.fromisoformat(last_reset_str).date()

            if 'modality_data' in state:
                for mod in allowed_modalities:
                    if mod in state['modality_data']:
                        mod_state = state['modality_data'][mod]
                        self._modality_data[mod]['skill_counts'] = mod_state.get(
                            'skill_counts', {skill: {} for skill in skill_columns}
                        )

                        last_reset_str = mod_state.get('last_reset_date')
                        if last_reset_str:
                            self._modality_data[mod]['last_reset_date'] = datetime.fromisoformat(last_reset_str).date()

            logger.info("State loaded successfully from disk")
        except Exception as e:
            logger.error(f"Failed to load state: {str(e)}", exc_info=True)

    def reset_for_testing(
        self,
        allowed_modalities: Optional[list] = None,
        skill_columns: Optional[list] = None,
    ) -> None:
        """Reset all state for testing purposes."""
        with self._lock:
            if allowed_modalities is None:
                allowed_modalities = list(self._modality_data.keys()) if self._modality_data else []
            if skill_columns is None:
                skill_columns = []

            self._global_worker_data = {
                'worker_ids': {},
                'weighted_counts': {},
                'assignments_per_mod': {mod: {} for mod in allowed_modalities},
                'last_reset_date': None
            }

            for mod in allowed_modalities:
                if mod in self._modality_data:
                    self._modality_data[mod] = {
                        'working_hours_df': None,
                        'info_texts': [],
                        'total_work_hours': {},
                        'worker_modifiers': {},
                        'skill_counts': {skill: {} for skill in skill_columns},
                        'last_reset_date': None
                    }

                if mod in self._staged_modality_data:
                    self._staged_modality_data[mod] = {
                        'working_hours_df': None,
                        'info_texts': [],
                        'total_work_hours': {},
                        'worker_modifiers': {},
                        'last_modified': None,
                        'last_prepped_at': None,
                        'last_prepped_by': None
                    }

            self._worker_skill_json_roster = {}
            self.work_hours_cache.invalidate()


# Module-level convenience function to get the singleton instance
def get_state() -> StateManager:
    """Get the StateManager singleton instance."""
    return StateManager.get_instance()
