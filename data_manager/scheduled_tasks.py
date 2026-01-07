"""
Scheduled tasks module for daily reset and preload operations.

This module handles:
- Daily reset at configured time (07:30 default)
- Next workday preload from master CSV
- Staged data clearing
"""
import os
import json
import shutil
from datetime import datetime, time
from typing import Dict, Any, Optional

from config import (
    APP_CONFIG,
    allowed_modalities,
    SKILL_COLUMNS,
    UPLOAD_FOLDER,
    selection_logger,
)
from lib.utils import (
    TIME_FORMAT,
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


def check_and_perform_daily_reset():
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
    from data_manager.file_ops import attempt_initialize_data, backup_dataframe
    from data_manager.state_persistence import save_state

    now = get_local_now()
    today = now.date()

    reset_time_str = APP_CONFIG.get('scheduler', {}).get('daily_reset_time', '07:30')
    try:
        reset_hour, reset_min = map(int, reset_time_str.split(':'))
        reset_time = time(reset_hour, reset_min)
    except Exception:
        reset_time = time(7, 30)

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

        # Process all modalities in a single global reset
        modalities_reset = []
        for mod, d in modality_data.items():
            # Reset per-modality tracking
            d['last_reset_date'] = today
            global_worker_data['assignments_per_mod'][mod] = {}
            d['skill_counts'] = {skill: {} for skill in SKILL_COLUMNS}

            # Try to load scheduled file for this modality
            scheduled_path = d['scheduled_file_path']
            try:
                if os.path.exists(scheduled_path):
                    context = f"daily reset {mod.upper()}"
                    success = attempt_initialize_data(
                        scheduled_path,
                        mod,
                        remove_on_failure=True,
                        context=context,
                    )
                    if success:
                        backup_dir = os.path.join(UPLOAD_FOLDER, "backups")
                        os.makedirs(backup_dir, exist_ok=True)
                        backup_file = os.path.join(backup_dir, os.path.basename(scheduled_path))
                        try:
                            shutil.move(scheduled_path, backup_file)
                            selection_logger.info("Scheduled daily file loaded and moved to backup for modality %s.", mod)
                        except OSError as exc:
                            selection_logger.warning("Scheduled Datei %s konnte nicht verschoben werden: %s", scheduled_path, exc)
                        backup_dataframe(mod)
                        modalities_reset.append(mod)
                    else:
                        selection_logger.warning("Scheduled file for %s war defekt und wurde entfernt.", mod)
                else:
                    selection_logger.debug(f"No scheduled file found for modality {mod}. Keeping old data.")
            except Exception as e:
                selection_logger.error(f"Error during daily reset for {mod}: {e}")

        selection_logger.info(f"Global daily reset completed. Modalities with new data: {modalities_reset or 'none'}")

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


def preload_next_workday(csv_path: str, config: dict) -> dict:
    """Load data from master CSV for the next workday and save to scheduled files."""
    # Import here to avoid circular imports
    from data_manager.csv_parser import build_working_hours_from_medweb

    try:
        next_day = get_next_workday()

        modality_dfs = build_working_hours_from_medweb(
            csv_path,
            next_day,
            config
        )

        if not modality_dfs:
            # No staff entries found - this is OK, not all shifts have staff (balancer handles this)
            date_str = next_day.strftime('%Y-%m-%d')
            selection_logger.info(f"No staff entries found for {date_str} - this is expected for some shifts")
            return {
                'success': True,
                'target_date': date_str,
                'message': f'Keine Mitarbeiter für {date_str} gefunden - Schichten können leer sein',
                'modalities_loaded': [],
                'total_workers': 0
            }

        saved_modalities = []
        total_workers = 0
        date_str = next_day.strftime('%Y-%m-%d')

        for modality, df in modality_dfs.items():
            d = modality_data[modality]
            target_path = d['scheduled_file_path']

            try:
                if df is None or df.empty:
                    selection_logger.info(f"No rows to preload for {modality} on {date_str}")
                    continue

                export_df = df.copy()
                export_df['TIME'] = export_df['start_time'].apply(lambda x: x.strftime(TIME_FORMAT)) + '-' + \
                                    export_df['end_time'].apply(lambda x: x.strftime(TIME_FORMAT))

                # Exclude internal columns from export
                cols_to_export = [
                    col for col in export_df.columns
                    if col not in ['start_time', 'end_time', 'shift_duration', 'canonical_id']
                ]
                export_df = export_df[cols_to_export]

                # Save as JSON
                scheduled_data = {
                    'working_hours': export_df.to_dict(orient='records'),
                    'info_texts': []
                }
                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(scheduled_data, f, ensure_ascii=False, indent=2, default=str)

                selection_logger.info(f"Scheduled file saved for {modality} at {target_path}")
                saved_modalities.append(modality)
                total_workers += len(df['PPL'].unique())

            except Exception as e:
                selection_logger.error(f"Failed to save scheduled file for {modality}: {str(e)}")

        if not saved_modalities:
            return {
                'success': False,
                'target_date': next_day.strftime('%Y-%m-%d'),
                'message': 'Fehler beim Speichern der Preload-Dateien'
            }

        return {
            'success': True,
            'target_date': date_str,
            'modalities_loaded': saved_modalities,
            'total_workers': total_workers,
            'message': f'Preload erfolgreich gespeichert (wird am {date_str} aktiviert)'
        }

    except Exception as e:
        selection_logger.error(f"Error in preload_next_workday: {str(e)}", exc_info=True)
        return {
            'success': False,
            'target_date': get_next_workday().strftime('%Y-%m-%d'),
            'message': f'Fehler beim Preload: {str(e)}'
        }
