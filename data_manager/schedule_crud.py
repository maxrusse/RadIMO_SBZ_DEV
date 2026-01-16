"""
Schedule CRUD operations module.

This module handles:
- Row-level schedule updates (update, add, delete)
- Gap handling with 4 resolution strategies
- Worker tracking reconciliation
- Overlapping shift resolution
"""
import json
import uuid
from datetime import datetime, time, date, timedelta
from typing import Optional, Dict, List, Tuple

import pandas as pd

from config import (
    allowed_modalities,
    SKILL_COLUMNS,
    selection_logger,
)
from lib.utils import (
    TIME_FORMAT,
    normalize_skill_value,
    calculate_shift_duration_hours,
    get_next_workday,
)
from state_manager import StateManager
from data_manager.file_ops import _calculate_total_work_hours

# Get state references
_state = StateManager.get_instance()
global_worker_data = _state.global_worker_data
modality_data = _state.modality_data
staged_modality_data = _state.staged_modality_data


def _validate_row_index(df: pd.DataFrame, row_index: int) -> bool:
    """Validate that row_index exists in DataFrame."""
    if df is None:
        return False
    return row_index in df.index


def _parse_gap_list(raw_val) -> list:
    """Parse gap list from various formats (None, list, JSON string)."""
    if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
        return []
    if isinstance(raw_val, list):
        return raw_val
    if isinstance(raw_val, str):
        try:
            return json.loads(raw_val)
        except Exception:
            return []
    return []


def _merge_gap(existing: list, new_gap: dict) -> list:
    """Merge a new gap into existing gap list, avoiding duplicates."""
    merged = existing.copy() if existing else []
    for g in merged:
        if (
            g.get('start') == new_gap.get('start') and
            g.get('end') == new_gap.get('end') and
            g.get('activity') == new_gap.get('activity')
        ):
            return merged
    merged.append(new_gap)
    return merged


def _calc_shift_duration_seconds(start_dt: datetime, end_dt: datetime) -> float:
    """Calculate shift duration in hours from datetime objects."""
    return (end_dt - start_dt).total_seconds() / 3600


def _get_schedule_data_dict(modality: str, use_staged: bool) -> dict:
    """Get the appropriate data dict (staged or live)."""
    if use_staged:
        return staged_modality_data[modality]
    return modality_data[modality]


def _get_staged_target_date() -> date:
    """Resolve the target date for staged prep data."""
    for mod_data in staged_modality_data.values():
        target_date = mod_data.get('target_date')
        if isinstance(target_date, date):
            return target_date
        if isinstance(target_date, str):
            try:
                return date.fromisoformat(target_date)
            except ValueError:
                continue
    return get_next_workday().date()


def _get_active_worker_names(df: Optional[pd.DataFrame]) -> set:
    """Get set of active worker names from DataFrame."""
    if df is None or df.empty or 'PPL' not in df.columns:
        return set()
    return {str(name).strip() for name in df['PPL'].dropna()}


def resolve_overlapping_shifts(shifts: List[dict], target_date: date) -> List[dict]:
    """
    Resolve overlapping shifts for the same worker. Same-day operations only.

    When two shifts overlap, the later shift wins:
    - Prior shift's end time is cropped to the beginning of the later shift
    - If a shift is completely covered by a later shift, it's removed
    - Shifts are sorted by start time first, then processed

    Args:
        shifts: List of shift dicts with 'PPL', 'start_time', 'end_time', etc.
        target_date: The target date for datetime calculations

    Returns:
        List of resolved shifts without overlaps
    """
    if not shifts or len(shifts) <= 1:
        return shifts

    # Group shifts by worker
    shifts_by_worker: Dict[str, List[dict]] = {}
    for shift in shifts:
        worker = shift.get('PPL', '')
        if worker not in shifts_by_worker:
            shifts_by_worker[worker] = []
        shifts_by_worker[worker].append(shift)

    result_shifts = []

    for worker, worker_shifts in shifts_by_worker.items():
        if len(worker_shifts) <= 1:
            result_shifts.extend(worker_shifts)
            continue

        # Sort by start time (earlier first)
        sorted_shifts = sorted(
            worker_shifts,
            key=lambda s: datetime.combine(target_date, s['start_time'])
        )

        resolved = []
        for i, current_shift in enumerate(sorted_shifts):
            current_start = current_shift['start_time']
            current_end = current_shift['end_time']

            current_start_dt = datetime.combine(target_date, current_start)
            current_end_dt = datetime.combine(target_date, current_end)
            # Same-day only: skip invalid shifts where end <= start
            if current_end_dt <= current_start_dt:
                continue

            # Check all later shifts to see if they overlap
            for j in range(i + 1, len(sorted_shifts)):
                later_shift = sorted_shifts[j]
                later_start = later_shift['start_time']

                later_start_dt = datetime.combine(target_date, later_start)

                # If later shift starts before current ends, crop current end
                if later_start_dt < current_end_dt:
                    current_end_dt = later_start_dt
                    current_end = later_start

            # If shift still has positive duration, add it
            if current_end_dt > current_start_dt:
                duration_hours = (current_end_dt - current_start_dt).total_seconds() / 3600

                # Only add if duration is meaningful (at least 6 minutes)
                if duration_hours >= 0.1:
                    resolved_shift = current_shift.copy()
                    resolved_shift['end_time'] = current_end
                    resolved_shift['shift_duration'] = duration_hours

                    # Update TIME field only if it was present in original shift
                    if 'TIME' in current_shift:
                        resolved_shift['TIME'] = f"{current_start.strftime(TIME_FORMAT)}-{current_end.strftime(TIME_FORMAT)}"

                    resolved.append(resolved_shift)
                    selection_logger.debug(
                        f"Shift for {worker}: {current_start.strftime(TIME_FORMAT)}-{current_end.strftime(TIME_FORMAT)} "
                        f"(duration: {duration_hours:.2f}h)"
                    )
                else:
                    selection_logger.info(
                        f"Removed zero-duration shift for {worker} "
                        f"(was {current_shift['start_time'].strftime(TIME_FORMAT)}-{current_shift['end_time'].strftime(TIME_FORMAT)})"
                    )

        result_shifts.extend(resolved)

    return result_shifts


def resolve_overlapping_shifts_df(df: pd.DataFrame, target_date: Optional[date] = None) -> pd.DataFrame:
    """
    Resolve overlapping shifts in a DataFrame.

    When two shifts overlap for the same worker, the later shift wins:
    - Prior shift's end time is cropped to the beginning of the later shift
    - Gaps (missing time) always win - they are not filled

    Args:
        df: DataFrame with 'PPL', 'start_time', 'end_time' columns
        target_date: Date for datetime calculations (defaults to today)

    Returns:
        DataFrame with resolved shifts (no overlaps)
    """
    if df is None or df.empty:
        return df

    if 'PPL' not in df.columns or 'start_time' not in df.columns or 'end_time' not in df.columns:
        return df

    # Use provided date or default to today
    base_date = target_date if target_date is not None else datetime.today().date()

    # Convert to list of dicts for processing
    shifts = df.to_dict('records')

    # Resolve overlaps
    resolved_shifts = resolve_overlapping_shifts(shifts, base_date)

    if not resolved_shifts:
        return pd.DataFrame(columns=df.columns)

    # Convert back to DataFrame
    result_df = pd.DataFrame(resolved_shifts)

    # Preserve column order from original
    cols = [c for c in df.columns if c in result_df.columns]
    extra_cols = [c for c in result_df.columns if c not in cols]
    result_df = result_df[cols + extra_cols]

    return result_df


def reconcile_live_worker_tracking(modality: Optional[str] = None) -> None:
    """
    Reconcile live worker tracking data after edits/deletions.

    Ensures skill_counts, weighted counts, and global assignment tracking
    only include workers currently present in the live schedules.
    """
    # Import here to avoid circular imports
    from data_manager.worker_management import get_canonical_worker_id

    active_workers_by_mod = {}
    active_canon_by_mod = {}
    all_active_canon = set()

    for mod in allowed_modalities:
        df = modality_data[mod].get('working_hours_df')
        active_workers = _get_active_worker_names(df)
        active_workers_by_mod[mod] = active_workers
        active_canon = {get_canonical_worker_id(name) for name in active_workers}
        active_canon_by_mod[mod] = active_canon
        all_active_canon.update(active_canon)

    modalities_to_reconcile = [modality] if modality else allowed_modalities

    for mod in modalities_to_reconcile:
        d = modality_data[mod]
        active_workers = active_workers_by_mod.get(mod, set())
        df = d.get('working_hours_df')

        new_skill_counts = {}
        for skill in SKILL_COLUMNS:
            counts = d['skill_counts'].get(skill, {})
            new_skill_counts[skill] = {name: counts.get(name, 0) for name in active_workers}
        d['skill_counts'] = new_skill_counts
        if df is None or df.empty:
            d['worker_modifiers'] = {}
            d['total_work_hours'] = {}
        else:
            d['worker_modifiers'] = df.groupby('PPL')['Modifier'].first().to_dict()
            d['total_work_hours'] = _calculate_total_work_hours(df)

        current_assignments = global_worker_data['assignments_per_mod'].get(mod, {})
        active_canon = active_canon_by_mod.get(mod, set())
        cleaned_assignments = {}
        for canonical_id in active_canon:
            if canonical_id in current_assignments:
                cleaned_assignments[canonical_id] = current_assignments[canonical_id]
            else:
                cleaned_assignments[canonical_id] = {skill: 0 for skill in SKILL_COLUMNS}
                cleaned_assignments[canonical_id]['total'] = 0
        global_worker_data['assignments_per_mod'][mod] = cleaned_assignments

    global_worker_data['weighted_counts'] = {
        canonical_id: global_worker_data['weighted_counts'].get(canonical_id, 0.0)
        for canonical_id in all_active_canon
    }


def _update_schedule_row(modality: str, row_index: int, updates: dict, use_staged: bool) -> tuple:
    """Update a single row in the schedule.

    Returns:
        (success: bool, error_or_info: str or dict)
        On success: (True, {'reindexed': bool}) - reindexed=True if DataFrame was rebuilt
        On failure: (False, error_message)
    """
    # Import here to avoid circular imports
    from data_manager.file_ops import backup_dataframe

    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    if not _validate_row_index(df, row_index):
        return False, 'Invalid row index'

    reindexed = False

    try:
        if 'PPL' in updates:
            return False, 'Worker renames are only allowed in the skill roster'
        for col, value in updates.items():
            if col in ['start_time', 'end_time']:
                df.at[row_index, col] = datetime.strptime(value, TIME_FORMAT).time()
            elif col in SKILL_COLUMNS:
                df.at[row_index, col] = normalize_skill_value(value)
            elif col == 'Modifier':
                df.at[row_index, col] = float(value)
            elif col == 'tasks':
                if isinstance(value, list):
                    df.at[row_index, 'tasks'] = ', '.join(value)
                else:
                    df.at[row_index, 'tasks'] = value
            elif col == 'gaps':
                df.at[row_index, 'gaps'] = value
            elif col == 'counts_for_hours':
                df.at[row_index, 'counts_for_hours'] = bool(value)

        if use_staged and 'is_manual' in df.columns:
            df.at[row_index, 'is_manual'] = True

        # Recalculate shift_duration if times changed (same-day only)
        if 'start_time' in updates or 'end_time' in updates:
            start = df.at[row_index, 'start_time']
            end = df.at[row_index, 'end_time']
            if pd.notnull(start) and pd.notnull(end):
                start_dt = datetime.combine(datetime.today(), start)
                end_dt = datetime.combine(datetime.today(), end)
                # Same-day only: duration is 0 if end <= start
                if end_dt > start_dt:
                    df.at[row_index, 'shift_duration'] = (end_dt - start_dt).total_seconds() / 3600
                else:
                    df.at[row_index, 'shift_duration'] = 0.0

                if 'TIME' in df.columns:
                    df.at[row_index, 'TIME'] = f"{start.strftime(TIME_FORMAT)}-{end.strftime(TIME_FORMAT)}"

            # Resolve any overlapping shifts for this worker (later shift wins)
            worker_name = df.at[row_index, 'PPL']
            worker_shifts = df[df['PPL'] == worker_name]
            if len(worker_shifts) > 1:
                # Use staged target date for prep data, today for live
                target_date = _get_staged_target_date() if use_staged else datetime.today().date()
                resolved_df = resolve_overlapping_shifts_df(df, target_date)
                if len(resolved_df) != len(df):
                    selection_logger.info(
                        f"Resolved overlapping shifts for {worker_name} after edit: "
                        f"{len(df)} -> {len(resolved_df)} rows"
                    )
                    reindexed = True
                data_dict['working_hours_df'] = resolved_df

        backup_dataframe(modality, use_staged=use_staged)
        return True, {'reindexed': reindexed}

    except ValueError as e:
        return False, f'Invalid time format: {e}'
    except Exception as e:
        return False, str(e)


def _add_worker_to_schedule(modality: str, worker_data: dict, use_staged: bool) -> tuple:
    """Add a new worker row to the schedule.

    Returns:
        (success: bool, row_index_or_info: int or dict, error: str or None)
        On success: (True, {'row_index': int, 'reindexed': bool}, None)
        On failure: (False, None, error_message)
    """
    # Import here to avoid circular imports
    from data_manager.file_ops import backup_dataframe

    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    reindexed = False

    try:
        ppl_name = worker_data.get('PPL', 'Neuer Worker (NW)')
        new_row = {
            'PPL': ppl_name,
            'start_time': datetime.strptime(worker_data.get('start_time', '07:00'), TIME_FORMAT).time(),
            'end_time': datetime.strptime(worker_data.get('end_time', '15:00'), TIME_FORMAT).time(),
            'Modifier': float(worker_data.get('Modifier', 1.0)),
        }

        # Only add TIME if the existing df has TIME column (for consistency)
        if df is not None and 'TIME' in df.columns:
            new_row['TIME'] = f"{new_row['start_time'].strftime(TIME_FORMAT)}-{new_row['end_time'].strftime(TIME_FORMAT)}"

        for skill in SKILL_COLUMNS:
            new_row[skill] = normalize_skill_value(worker_data.get(skill, 0))

        tasks = worker_data.get('tasks', [])
        if isinstance(tasks, list):
            new_row['tasks'] = ', '.join(tasks)
        else:
            new_row['tasks'] = tasks or ''

        start_dt = datetime.combine(datetime.today(), new_row['start_time'])
        end_dt = datetime.combine(datetime.today(), new_row['end_time'])
        # Same-day only: duration is 0 if end <= start
        if end_dt > start_dt:
            new_row['shift_duration'] = (end_dt - start_dt).total_seconds() / 3600
        else:
            new_row['shift_duration'] = 0.0

        new_row['counts_for_hours'] = worker_data.get('counts_for_hours', True)

        if df is None or df.empty:
            data_dict['working_hours_df'] = pd.DataFrame([new_row])
        else:
            data_dict['working_hours_df'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        if use_staged:
            if 'is_manual' not in data_dict['working_hours_df'].columns:
                data_dict['working_hours_df']['is_manual'] = False
            new_row_idx = len(data_dict['working_hours_df']) - 1
            data_dict['working_hours_df'].at[new_row_idx, 'is_manual'] = True

        # Resolve any overlapping shifts for this worker (later shift wins)
        df = data_dict['working_hours_df']
        original_len = len(df)
        worker_shifts = df[df['PPL'] == ppl_name]
        if len(worker_shifts) > 1:
            # Use staged target date for prep data, today for live
            target_date = _get_staged_target_date() if use_staged else datetime.today().date()
            resolved_df = resolve_overlapping_shifts_df(df, target_date)
            if len(resolved_df) != original_len:
                selection_logger.info(
                    f"Resolved overlapping shifts for {ppl_name} after add: "
                    f"{original_len} -> {len(resolved_df)} rows"
                )
                reindexed = True
            data_dict['working_hours_df'] = resolved_df

        backup_dataframe(modality, use_staged=use_staged)
        new_idx = len(data_dict['working_hours_df']) - 1
        return True, {'row_index': new_idx, 'reindexed': reindexed}, None

    except ValueError as e:
        return False, None, f'Invalid time format: {e}'
    except Exception as e:
        return False, None, str(e)


def _delete_worker_from_schedule(modality: str, row_index: int, use_staged: bool, verify_ppl: Optional[str] = None) -> tuple:
    """Delete a worker row from the schedule."""
    # Import here to avoid circular imports
    from data_manager.file_ops import backup_dataframe

    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    try:
        row_index_int = int(row_index)
    except (TypeError, ValueError):
        return False, None, 'Invalid row index'

    if not _validate_row_index(df, row_index_int):
        return False, None, 'Invalid row index'

    try:
        worker_name = df.loc[row_index_int, 'PPL']
        gap_id = df.loc[row_index_int, 'gap_id'] if 'gap_id' in df.columns else None

        if verify_ppl and str(worker_name) != str(verify_ppl):
            return False, None, 'Row mismatch: Schedule has changed. Please reload.'

        if gap_id and pd.notnull(gap_id):
            # Delete all rows sharing the same gap_id
            data_dict['working_hours_df'] = df[df['gap_id'] != gap_id].reset_index(drop=True)
            selection_logger.info(f"Deleted linked gap rows for ID {gap_id}")
        else:
            data_dict['working_hours_df'] = df.drop(index=row_index_int).reset_index(drop=True)

        if not use_staged:
            reconcile_live_worker_tracking(modality)

        backup_dataframe(modality, use_staged=use_staged)
        return True, worker_name, None

    except Exception as e:
        return False, None, str(e)


def _add_gap_to_schedule(modality: str, row_index: int, gap_type: str, gap_start: str, gap_end: str, use_staged: bool) -> tuple:
    """
    Add a gap to a worker's schedule.

    Handles 4 cases:
    1. Gap covers entire shift - delete row(s)
    2. Gap at start - adjust start time
    3. Gap at end - adjust end time
    4. Gap in middle - split into two rows
    """
    # Import here to avoid circular imports
    from data_manager.file_ops import backup_dataframe

    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    if df is not None:
        if 'gaps' not in df.columns:
            df['gaps'] = None
        if 'gap_id' not in df.columns:
            df['gap_id'] = None
        if use_staged and 'is_manual' not in df.columns:
            df['is_manual'] = False

    if not _validate_row_index(df, row_index):
        return False, None, 'Invalid row index'

    try:
        row = df.loc[row_index].copy()
        worker_name = row['PPL']

        gap_start_time = datetime.strptime(gap_start, TIME_FORMAT).time()
        gap_end_time = datetime.strptime(gap_end, TIME_FORMAT).time()

        if gap_start_time >= gap_end_time:
            return False, None, 'Gap start time must be before gap end time'

        shift_start = row['start_time']
        shift_end = row['end_time']

        base_date = datetime.today()
        shift_start_dt = datetime.combine(base_date, shift_start)
        shift_end_dt = datetime.combine(base_date, shift_end)
        gap_start_dt = datetime.combine(base_date, gap_start_time)
        gap_end_dt = datetime.combine(base_date, gap_end_time)

        gap_entry = {
            'start': gap_start_time.strftime(TIME_FORMAT),
            'end': gap_end_time.strftime(TIME_FORMAT),
            'activity': gap_type,
        }

        # Get existing gap_id from row (if this shift is part of a linked gap group)
        existing_gap_id = row.get('gap_id') if 'gap_id' in df.columns else None
        if pd.isna(existing_gap_id):
            existing_gap_id = None

        if gap_end_dt <= shift_start_dt or gap_start_dt >= shift_end_dt:
            return False, None, 'Gap is outside worker shift times'

        log_prefix = "STAGED: " if use_staged else ""
        merged_gaps = json.dumps(_merge_gap(_parse_gap_list(row.get('gaps')), gap_entry))

        # Helper to update TIME column if it exists
        def update_time_col(idx, start_t, end_t):
            if 'TIME' in df.columns:
                df.at[idx, 'TIME'] = f"{start_t.strftime(TIME_FORMAT)}-{end_t.strftime(TIME_FORMAT)}"

        if gap_start_dt <= shift_start_dt and gap_end_dt >= shift_end_dt:
            # Case 1: Gap covers entire shift - delete row(s)
            if existing_gap_id:
                data_dict['working_hours_df'] = df[df['gap_id'] != existing_gap_id].reset_index(drop=True)
            else:
                data_dict['working_hours_df'] = df.drop(index=row_index).reset_index(drop=True)

            backup_dataframe(modality, use_staged=use_staged)
            selection_logger.info(f"{log_prefix}Gap ({gap_type}) covers entire shift for {worker_name} - row(s) deleted")
            return True, 'deleted', None

        elif gap_start_dt <= shift_start_dt < gap_end_dt < shift_end_dt:
            # Case 2: Gap at start - adjust start time
            df.at[row_index, 'start_time'] = gap_end_time
            update_time_col(row_index, gap_end_time, shift_end)
            new_start_dt = datetime.combine(base_date, gap_end_time)
            df.at[row_index, 'shift_duration'] = _calc_shift_duration_seconds(new_start_dt, shift_end_dt)
            df.at[row_index, 'gaps'] = merged_gaps
            backup_dataframe(modality, use_staged=use_staged)
            selection_logger.info(f"{log_prefix}Gap ({gap_type}) at start for {worker_name}: new start {gap_end_time}")
            return True, 'start_adjusted', None

        elif shift_start_dt < gap_start_dt < shift_end_dt and gap_end_dt >= shift_end_dt:
            # Case 3: Gap at end - adjust end time
            df.at[row_index, 'end_time'] = gap_start_time
            update_time_col(row_index, shift_start, gap_start_time)
            new_end_dt = datetime.combine(base_date, gap_start_time)
            df.at[row_index, 'shift_duration'] = _calc_shift_duration_seconds(shift_start_dt, new_end_dt)
            df.at[row_index, 'gaps'] = merged_gaps
            backup_dataframe(modality, use_staged=use_staged)
            selection_logger.info(f"{log_prefix}Gap ({gap_type}) at end for {worker_name}: new end {gap_start_time}")
            return True, 'end_adjusted', None

        else:
            # Case 4: Gap in middle - SPLIT into two rows
            new_gap_id = f"gap_{uuid.uuid4().hex[:12]}"
            new_end_dt = datetime.combine(base_date, gap_start_time)
            new_start_dt = datetime.combine(base_date, gap_end_time)

            # Update existing row (first half)
            df.at[row_index, 'end_time'] = gap_start_time
            update_time_col(row_index, shift_start, gap_start_time)
            df.at[row_index, 'shift_duration'] = _calc_shift_duration_seconds(shift_start_dt, new_end_dt)
            df.at[row_index, 'gap_id'] = new_gap_id
            df.at[row_index, 'gaps'] = merged_gaps
            if use_staged:
                df.at[row_index, 'is_manual'] = True

            # Create new row (second half)
            new_row = row.to_dict()
            new_row['start_time'] = gap_end_time
            new_row['end_time'] = shift_end
            new_row['shift_duration'] = _calc_shift_duration_seconds(new_start_dt, shift_end_dt)
            new_row['gap_id'] = new_gap_id
            new_row['gaps'] = merged_gaps
            if 'TIME' in df.columns:
                new_row['TIME'] = f"{gap_end_time.strftime(TIME_FORMAT)}-{shift_end.strftime(TIME_FORMAT)}"
            if use_staged:
                new_row['is_manual'] = True

            data_dict['working_hours_df'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            backup_dataframe(modality, use_staged=use_staged)
            selection_logger.info(f"{log_prefix}Gap ({gap_type}) in middle for {worker_name}: split into two shifts with ID {new_gap_id}")
            return True, 'split', None

    except ValueError as e:
        return False, None, f'Invalid time format: {e}'
    except Exception as e:
        return False, None, str(e)
