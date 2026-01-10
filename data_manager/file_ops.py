"""
File operations module for backup, restore, and data loading.

This module handles:
- DataFrame backup to JSON
- Loading staged/scheduled data files
- Data initialization from JSON
- File quarantine for corrupted files
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config import (
    allowed_modalities,
    APP_CONFIG,
    SKILL_COLUMNS,
    UPLOAD_FOLDER,
    SKILL_ROSTER_AUTO_IMPORT,
    selection_logger,
)
from lib.utils import (
    TIME_FORMAT,
    get_local_now,
    parse_time_range,
    calculate_shift_duration_hours,
    validate_excel_structure,
    normalize_skill_value,
)
from data_manager.worker_management import (
    apply_skill_overrides,
    get_canonical_worker_id,
    get_merged_worker_roster,
    get_worker_skill_mod_combinations,
)
from state_manager import StateManager

# Get state references
_state = StateManager.get_instance()
lock = _state.lock
global_worker_data = _state.global_worker_data
modality_data = _state.modality_data
staged_modality_data = _state.staged_modality_data


def apply_roster_overrides_to_schedule(df: pd.DataFrame, modality: str) -> pd.DataFrame:
    """Reapply roster skill constraints to a schedule DataFrame."""
    if df is None or df.empty or 'PPL' not in df.columns:
        return df

    worker_roster = get_merged_worker_roster(APP_CONFIG)

    for idx, row in df.iterrows():
        canonical_id = get_canonical_worker_id(row.get('PPL'))
        roster_combinations = get_worker_skill_mod_combinations(canonical_id, worker_roster)
        overrides = {}

        for skill in SKILL_COLUMNS:
            if skill not in df.columns:
                continue
            normalized = normalize_skill_value(row.get(skill))
            if normalized == 'w':
                override_value = 1
            else:
                try:
                    override_value = int(normalized)
                except (TypeError, ValueError):
                    override_value = 0
            overrides[f"{skill}_{modality}"] = override_value

        final_combinations = apply_skill_overrides(roster_combinations, overrides)

        for skill in SKILL_COLUMNS:
            key = f"{skill}_{modality}"
            if skill in df.columns and key in final_combinations:
                df.at[idx, skill] = final_combinations[key]

    return df


def _calculate_total_work_hours(df: pd.DataFrame) -> dict:
    """Calculate total work hours per worker from DataFrame."""
    if df is None or df.empty:
        return {}

    if 'shift_duration' not in df.columns:
        return {}

    if 'counts_for_hours' in df.columns:
        # Default to True (count for hours) if value is missing
        hours_df = df[df['counts_for_hours'].fillna(True).astype(bool)]
    else:
        hours_df = df

    if hours_df.empty:
        return {}

    return hours_df.groupby('PPL')['shift_duration'].sum().to_dict()


def backup_dataframe(modality: str, use_staged: bool = False):
    """Backup DataFrame to JSON file."""
    d = staged_modality_data[modality] if use_staged else modality_data[modality]
    if d['working_hours_df'] is not None:
        backup_dir = os.path.join(UPLOAD_FOLDER, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        suffix = "_staged" if use_staged else "_live"
        backup_file = os.path.join(backup_dir, f"Cortex_{modality.upper()}{suffix}.json")
        try:
            df_backup = d['working_hours_df'].copy()

            if 'TIME' not in df_backup.columns and {'start_time', 'end_time'}.issubset(df_backup.columns):
                def _fmt_time(value):
                    if pd.isna(value):
                        return ''
                    return value.strftime(TIME_FORMAT) if hasattr(value, 'strftime') else str(value)

                df_backup['TIME'] = (
                    df_backup['start_time'].apply(_fmt_time) +
                    '-' +
                    df_backup['end_time'].apply(_fmt_time)
                )

            cols_to_backup = [
                col for col in df_backup.columns
                if col not in ['start_time', 'end_time', 'shift_duration', 'canonical_id']
            ]
            df_backup = df_backup[cols_to_backup].copy()

            # Convert DataFrame to JSON-serializable format
            backup_data = {
                'working_hours': df_backup.to_dict(orient='records'),
                'info_texts': d.get('info_texts', [])
            }
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

            mode_label = "staged" if use_staged else "live"
            selection_logger.info(f"{mode_label.capitalize()} backup updated for modality {modality} at {backup_file}")

            if use_staged:
                d['last_modified'] = get_local_now()
                d['last_prepped_at'] = d['last_modified'].strftime('%d.%m.%Y %H:%M')
        except Exception as e:
            mode_label = "staged" if use_staged else "live"
            selection_logger.error(f"Error backing up {mode_label} DataFrame for modality {modality}: {e}")


def load_staged_dataframe(modality: str) -> bool:
    """
    Load staged or scheduled dataframe for a modality from JSON.

    Uses try/except instead of os.path.exists to prevent TOCTOU race conditions
    (file could be deleted between check and open).
    """
    d = staged_modality_data[modality]
    staged_file = d['staged_file_path']
    scheduled_file = modality_data[modality]['scheduled_file_path']

    # Helper function to load JSON file and process it
    def _load_json(file_path: str) -> bool:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'working_hours' not in data:
                selection_logger.warning(f"File {file_path} missing 'working_hours' key")
                return False

            df = pd.DataFrame(data['working_hours'])

            if 'TIME' in df.columns:
                time_data = df['TIME'].apply(parse_time_range)
                df['start_time'] = time_data.apply(lambda x: x[0])
                df['end_time'] = time_data.apply(lambda x: x[1])
                df['shift_duration'] = df.apply(
                    lambda row: calculate_shift_duration_hours(row['start_time'], row['end_time']),
                    axis=1
                )

            if 'counts_for_hours' not in df.columns:
                df['counts_for_hours'] = True

            d['working_hours_df'] = df
            d['total_work_hours'] = _calculate_total_work_hours(df)
            d['info_texts'] = data.get('info_texts', [])

            try:
                d['last_modified'] = datetime.fromtimestamp(os.path.getmtime(file_path))
            except OSError:
                d['last_modified'] = get_local_now()

            selection_logger.info(f"Loaded staged data for {modality} from {file_path}")
            return True
        except FileNotFoundError:
            # File doesn't exist - caller should try fallback
            raise
        except Exception as e:
            selection_logger.error(f"Error loading staged data for {modality} from {file_path}: {e}")
            return False

    # Try staged file first, fall back to scheduled file
    try:
        return _load_json(staged_file)
    except FileNotFoundError:
        pass

    # Staged file not found, try scheduled file
    try:
        selection_logger.info(f"No staged file for {modality}, falling back to scheduled file: {scheduled_file}")
        return _load_json(scheduled_file)
    except FileNotFoundError:
        selection_logger.info(f"No staged or scheduled file found for {modality}")
        return False


def quarantine_file(file_path: str, reason: str) -> Optional[str]:
    """
    Move a defective file to quarantine directory.

    Uses try/except instead of os.path.exists to prevent TOCTOU race condition
    (file could be deleted between check and move).
    """
    if not file_path:
        return None

    invalid_dir = Path(UPLOAD_FOLDER) / 'invalid'
    invalid_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    original = Path(file_path)
    target = invalid_dir / f"{original.stem}_{timestamp}{original.suffix or '.json'}"

    try:
        shutil.move(str(original), str(target))
        selection_logger.warning("Defekte Datei '%s' nach '%s' verschoben (%s)", file_path, target, reason)
        return str(target)
    except FileNotFoundError:
        # File was already deleted - not an error, just log and return
        selection_logger.debug("Datei '%s' existiert nicht mehr (bereits gelöscht)", file_path)
        return None
    except OSError as exc:
        selection_logger.warning("Datei '%s' konnte nicht verschoben werden (%s): %s", file_path, reason, exc)
        return None


def initialize_data(file_path: str, modality: str):
    """Initialize modality data from JSON file."""
    # Import here to avoid circular imports
    from data_manager.worker_management import (
        invalidate_work_hours_cache,
        auto_populate_skill_roster,
    )

    d = modality_data[modality]
    d['skill_counts'] = {skill: {} for skill in SKILL_COLUMNS}
    global_worker_data['assignments_per_mod'][modality] = {}

    with lock:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'working_hours' not in data:
                raise ValueError("'working_hours' key not found in JSON")

            df = pd.DataFrame(data['working_hours'])
            required_columns = ['PPL', 'TIME']
            valid, error_msg = validate_excel_structure(df, required_columns, SKILL_COLUMNS)
            if not valid:
                raise ValueError(error_msg)

            if 'Modifier' not in df.columns:
                df['Modifier'] = 1.0
            else:
                df['Modifier'] = (
                    df['Modifier']
                    .fillna(1.0)
                    .astype(str)
                    .str.replace(',', '.')
                    .astype(float)
                )

            df['start_time'], df['end_time'] = zip(*df['TIME'].map(parse_time_range))

            for skill in SKILL_COLUMNS:
                if skill not in df.columns:
                    df[skill] = 0
                df[skill] = df[skill].fillna(0).apply(normalize_skill_value)

            df = apply_roster_overrides_to_schedule(df, modality)

            df['shift_duration'] = df.apply(
                lambda row: calculate_shift_duration_hours(row['start_time'], row['end_time']),
                axis=1
            )

            col_order = ['PPL', 'Modifier', 'TIME', 'start_time', 'end_time', 'shift_duration', 'tasks', 'counts_for_hours']
            skill_cols = [skill for skill in SKILL_COLUMNS if skill in df.columns]
            col_order = col_order[:3] + skill_cols + col_order[3:]

            if 'tasks' not in df.columns:
                df['tasks'] = ''
            if 'counts_for_hours' not in df.columns:
                df['counts_for_hours'] = True

            df = df[[col for col in col_order if col in df.columns]]

            d['working_hours_df'] = df
            # Invalidate work hours cache when data changes
            invalidate_work_hours_cache(modality)
            d['worker_modifiers'] = df.groupby('PPL')['Modifier'].first().to_dict()
            d['total_work_hours'] = _calculate_total_work_hours(df)
            unique_workers = df['PPL'].unique()

            d['skill_counts'] = {}
            for skill in SKILL_COLUMNS:
                if skill in df.columns:
                    d['skill_counts'][skill] = {w: 0 for w in unique_workers}
                else:
                    d['skill_counts'][skill] = {}

            d['info_texts'] = data.get('info_texts', [])

            if SKILL_ROSTER_AUTO_IMPORT:
                auto_populate_skill_roster({modality: df})  # Returns tuple, ignore here

        except Exception as e:
            error_message = f"Fehler beim Laden der JSON-Datei für Modality '{modality}': {str(e)}"
            selection_logger.error(error_message)
            selection_logger.exception("Stack trace:")
            raise ValueError(error_message)


def attempt_initialize_data(
    file_path: str,
    modality: str,
    *,
    remove_on_failure: bool = False,
    context: str = ''
) -> bool:
    """Attempt to initialize data with error handling."""
    try:
        initialize_data(file_path, modality)
        return True
    except Exception as exc:
        selection_logger.error(
            "Fehler beim Initialisieren der Datei %s für %s (%s): %s",
            file_path, modality, context or 'runtime', exc,
        )
        if remove_on_failure:
            quarantine_file(file_path, f"{context or 'runtime'}: {exc}")
        return False
