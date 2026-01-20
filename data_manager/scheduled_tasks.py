"""
Scheduled tasks module for daily reset and preload operations.

This module handles:
- Daily reset at configured time (07:30 default)
- Next workday preload from master CSV
- Staged data clearing
"""
import os
import shutil
from datetime import datetime, time, date
from typing import Any, Dict, Optional, Union

from config import (
    APP_CONFIG,
    allowed_modalities,
    SKILL_COLUMNS,
    UPLOAD_FOLDER,
    selection_logger,
)
from lib.utils import (
    get_local_now,
    get_next_workday,
)
from state_manager import StateManager

# Get state references
_state = StateManager.get_instance()
lock = _state.lock
global_worker_data = _state.global_worker_data
modality_data = _state.modality_data
staged_modality_data = _state.staged_modality_data


def _parse_reset_time(reset_time_str: str) -> time:
    try:
        reset_hour, reset_min = map(int, reset_time_str.split(':'))
    except ValueError:
        return time(7, 30)
    return time(reset_hour, reset_min)


def check_and_perform_daily_reset() -> None:
    """
    Perform a single global daily reset at the configured reset time.

    Uses atomic check-and-set with locking to prevent race conditions when
    multiple threads/requests trigger this simultaneously at 07:30.

    This is ONE global reset (not per-modality) that:
    1. Resets global weighted counts
    2. Resets all modality counters
    3. Loads scheduled files for all modalities
    """
    # Import here to avoid circular imports
    from data_manager.worker_management import invalidate_work_hours_cache
    from data_manager.file_ops import (
        backup_dataframe,
        initialize_data_from_unified,
    )
    from data_manager.state_persistence import save_state

    now = get_local_now()
    today = now.date()

    reset_time_str = APP_CONFIG.get('scheduler', {}).get('daily_reset_time', '07:30')
    reset_time = _parse_reset_time(reset_time_str)

    # Quick check without lock to avoid unnecessary locking on most requests
    if global_worker_data['last_reset_date'] == today:
        return
    if now.time() < reset_time:
        return

    # Atomic check-and-set with lock to prevent multiple threads from resetting
    with lock:
        # Double-check after acquiring lock (another thread may have just reset)
        if global_worker_data['last_reset_date'] == today:
            return

        selection_logger.info("Starting global daily reset for all modalities")

        # Invalidate all work hours caches at start of reset
        invalidate_work_hours_cache()

        # Mark reset date FIRST (atomic check-and-set pattern)
        # This prevents other threads from entering even if we fail midway
        global_worker_data['last_reset_date'] = today

        # Reset global weighted counts
        global_worker_data['weighted_counts'] = {}

        # Reset per-modality tracking
        for mod, d in modality_data.items():
            d['last_reset_date'] = today
            global_worker_data['assignments_per_mod'][mod] = {}
            d['skill_counts'] = {skill: {} for skill in SKILL_COLUMNS}

        scheduled_path = _state.unified_schedule_paths['scheduled']

        try:
            if os.path.exists(scheduled_path):
                if initialize_data_from_unified(scheduled_path, context="daily reset unified"):
                    backup_dir = os.path.join(UPLOAD_FOLDER, "backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    backup_file = _state.unified_schedule_paths['scheduled_backup']
                    try:
                        shutil.move(scheduled_path, backup_file)
                        selection_logger.info("Unified scheduled file loaded and moved to backup.")
                    except OSError as exc:
                        selection_logger.warning("Scheduled Datei %s konnte nicht verschoben werden: %s", scheduled_path, exc)
                    backup_dataframe(allowed_modalities[0])
                else:
                    selection_logger.warning("Unified scheduled file was invalid and was not loaded.")
            else:
                selection_logger.debug("No unified scheduled file found. Keeping old data.")
        except Exception as exc:
            selection_logger.error("Error during daily reset for unified schedule: %s", exc)

        selection_logger.info("Global daily reset completed.")

    # Save state OUTSIDE the lock to prevent blocking I/O
    save_state()


def clear_staged_data(modality: Optional[str] = None) -> Dict[str, Any]:
    """Clear staged data for one or all modalities."""
    cleared = []
    modalities_to_clear = [modality] if modality else allowed_modalities

    for mod in modalities_to_clear:
        if mod in staged_modality_data:
            old_df = staged_modality_data[mod].get('working_hours_df')
            row_count = len(old_df) if old_df is not None else 0

            staged_modality_data[mod]['working_hours_df'] = None
            staged_modality_data[mod]['info_texts'] = []
            staged_modality_data[mod]['total_work_hours'] = {}
            staged_modality_data[mod]['worker_modifiers'] = {}
            staged_modality_data[mod]['last_modified'] = None

            if row_count > 0:
                cleared.append({'modality': mod, 'rows_cleared': row_count})

    return {'cleared': cleared, 'total_modalities': len(cleared)}


def _parse_target_date(value: Optional[Union[str, date, datetime]]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def preload_next_workday(csv_path: str, config: dict, target_date: Optional[Union[str, date, datetime]] = None) -> Dict[str, Any]:
    """Load data from master CSV for the target date and save to scheduled files."""
    # Import here to avoid circular imports
    from data_manager.csv_parser import build_working_hours_from_medweb
    from data_manager.file_ops import write_unified_scheduled_file

    try:
        resolved_date = _parse_target_date(target_date) or get_next_workday().date()
        target_dt = datetime.combine(resolved_date, datetime.min.time())
        date_str = resolved_date.strftime('%Y-%m-%d')

        modality_dfs = build_working_hours_from_medweb(
            csv_path,
            target_dt,
            config
        )

        # Clear unified scheduled file first to prevent stale data
        unified_scheduled_path = _state.unified_schedule_paths['scheduled']
        if os.path.exists(unified_scheduled_path):
            try:
                os.remove(unified_scheduled_path)
                selection_logger.info("Cleared old unified scheduled file")
            except OSError as e:
                selection_logger.warning("Could not remove old unified scheduled file: %s", e)

        if not modality_dfs:
            modality_dfs = {}

        saved_modalities = []
        total_workers = 0

        try:
            for modality, df in modality_dfs.items():
                if df is None or df.empty:
                    selection_logger.info(f"No rows to preload for {modality} on {date_str}")
                    continue
                saved_modalities.append(modality)
                total_workers += len(df['PPL'].unique())

            write_unified_scheduled_file(modality_dfs, target_date=resolved_date)
        except Exception as exc:
            selection_logger.error("Failed to save unified scheduled file: %s", exc)

        if not saved_modalities:
            selection_logger.info(f"No staff entries found for {date_str} - this is expected for some shifts")

        with lock:
            global_worker_data['last_preload_date'] = resolved_date
        from data_manager.state_persistence import save_state
        save_state()

        return {
            'success': True,
            'target_date': date_str,
            'modalities_loaded': saved_modalities,
            'total_workers': total_workers,
            'message': (
                f'Keine Mitarbeiter für {date_str} gefunden - Schichten können leer sein'
                if not saved_modalities
                else f'Preload erfolgreich gespeichert (wird am {date_str} aktiviert)'
            )
        }

    except Exception as exc:
        selection_logger.error(f"Error in preload_next_workday: {exc}", exc_info=True)
        return {
            'success': False,
            'target_date': (_parse_target_date(target_date) or get_next_workday().date()).strftime('%Y-%m-%d'),
            'message': f'Fehler beim Preload: {exc}'
        }
