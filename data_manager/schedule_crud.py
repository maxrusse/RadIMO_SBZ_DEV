"""
Schedule CRUD operations module.

This module handles:
- Row-level schedule updates (update, add, delete)
- Gap rows (independent entries that override shift availability)
- Worker tracking reconciliation
- Overlapping shift resolution
"""
from datetime import datetime, time, date
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
from data_manager.file_ops import _calculate_total_work_hours, backup_dataframe

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


def _ensure_row_type_column(df: pd.DataFrame) -> None:
    if df is None:
        return
    if 'row_type' not in df.columns:
        df['row_type'] = 'shift'
    else:
        df['row_type'] = df['row_type'].fillna('shift')


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _subtract_intervals(base: Tuple[int, int], gaps: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    remaining = [base]
    for gap_start, gap_end in gaps:
        next_remaining = []
        for start, end in remaining:
            if gap_end <= start or gap_start >= end:
                next_remaining.append((start, end))
                continue
            if gap_start > start:
                next_remaining.append((start, gap_start))
            if gap_end < end:
                next_remaining.append((gap_end, end))
        remaining = next_remaining
        if not remaining:
            break
    return remaining


def _recalculate_worker_shift_durations(df: pd.DataFrame, worker_name: str) -> None:
    if df is None or df.empty:
        return
    _ensure_row_type_column(df)
    worker_rows = df[df['PPL'] == worker_name]
    if worker_rows.empty:
        return
    gap_rows = worker_rows[worker_rows['row_type'] == 'gap']
    gap_intervals: List[Tuple[int, int]] = []
    for _, gap_row in gap_rows.iterrows():
        if bool(gap_row.get('counts_for_hours', False)):
            continue
        start = gap_row.get('start_time')
        end = gap_row.get('end_time')
        if pd.isna(start) or pd.isna(end):
            continue
        gap_intervals.append((_time_to_minutes(start), _time_to_minutes(end)))
    gap_intervals = _merge_intervals([g for g in gap_intervals if g[1] > g[0]])

    for idx, row in worker_rows[worker_rows['row_type'] != 'gap'].iterrows():
        start = row.get('start_time')
        end = row.get('end_time')
        if pd.isna(start) or pd.isna(end):
            df.at[idx, 'shift_duration'] = 0.0
            df.at[idx, 'counts_for_hours'] = False
            continue
        start_min = _time_to_minutes(start)
        end_min = _time_to_minutes(end)
        if end_min <= start_min:
            df.at[idx, 'shift_duration'] = 0.0
            df.at[idx, 'counts_for_hours'] = False
            continue
        remaining = _subtract_intervals((start_min, end_min), gap_intervals)
        total_minutes = sum(seg_end - seg_start for seg_start, seg_end in remaining)
        df.at[idx, 'shift_duration'] = round(total_minutes / 60.0, 4)
        if total_minutes <= 0:
            df.at[idx, 'counts_for_hours'] = False


def _coerce_bool(value: Optional[object]) -> Optional[bool]:
    """Normalize various truthy/falsey inputs into a bool or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'true', '1', 'yes', 'y'}
    return bool(value)


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

    _ensure_row_type_column(df)
    shift_rows = df[df['row_type'] != 'gap']
    gap_rows = df[df['row_type'] == 'gap']

    # Convert to list of dicts for processing
    shifts = shift_rows.to_dict('records')

    # Resolve overlaps
    resolved_shifts = resolve_overlapping_shifts(shifts, base_date)

    if not resolved_shifts:
        result_df = pd.DataFrame(columns=df.columns)
        if not gap_rows.empty:
            result_df = pd.concat([result_df, gap_rows], ignore_index=True)
        return result_df

    # Convert back to DataFrame
    result_df = pd.DataFrame(resolved_shifts)
    if not gap_rows.empty:
        result_df = pd.concat([result_df, gap_rows], ignore_index=True)

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
    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']
    _ensure_row_type_column(df)

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
            elif col == 'counts_for_hours':
                df.at[row_index, 'counts_for_hours'] = bool(value)
            elif col == 'row_type':
                df.at[row_index, 'row_type'] = value

        if use_staged and 'is_manual' in df.columns:
            df.at[row_index, 'is_manual'] = True

        # Recalculate shift_duration if times changed (same-day only)
        if 'start_time' in updates or 'end_time' in updates:
            start = df.at[row_index, 'start_time']
            end = df.at[row_index, 'end_time']
            if pd.notnull(start) and pd.notnull(end) and 'TIME' in df.columns:
                df.at[row_index, 'TIME'] = f"{start.strftime(TIME_FORMAT)}-{end.strftime(TIME_FORMAT)}"

            worker_name = df.at[row_index, 'PPL']
            target_date = _get_staged_target_date() if use_staged else datetime.today().date()
            resolved_df = resolve_overlapping_shifts_df(df, target_date)
            if len(resolved_df) != len(df):
                selection_logger.info(
                    f"Resolved overlapping shifts for {worker_name} after edit: "
                    f"{len(df)} -> {len(resolved_df)} rows"
                )
                reindexed = True
            data_dict['working_hours_df'] = resolved_df
            df = data_dict['working_hours_df']

        if 'row_type' in updates or 'counts_for_hours' in updates or 'start_time' in updates or 'end_time' in updates:
            worker_name = df.at[row_index, 'PPL']
            _recalculate_worker_shift_durations(df, worker_name)

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
    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    reindexed = False

    try:
        ppl_name = worker_data.get('PPL', 'Neuer Worker (NW)')
        row_type = worker_data.get('row_type', 'shift')
        new_row = {
            'PPL': ppl_name,
            'start_time': datetime.strptime(worker_data.get('start_time', '07:00'), TIME_FORMAT).time(),
            'end_time': datetime.strptime(worker_data.get('end_time', '15:00'), TIME_FORMAT).time(),
            'Modifier': float(worker_data.get('Modifier', 1.0)),
            'row_type': row_type,
        }

        # Only add TIME if the existing df has TIME column (for consistency)
        if df is not None and 'TIME' in df.columns:
            new_row['TIME'] = f"{new_row['start_time'].strftime(TIME_FORMAT)}-{new_row['end_time'].strftime(TIME_FORMAT)}"

        for skill in SKILL_COLUMNS:
            default_value = -1 if row_type == 'gap' else 0
            new_row[skill] = normalize_skill_value(worker_data.get(skill, default_value))

        tasks = worker_data.get('tasks', [])
        if isinstance(tasks, list):
            new_row['tasks'] = ', '.join(tasks)
        else:
            new_row['tasks'] = tasks or ''

        start_dt = datetime.combine(datetime.today(), new_row['start_time'])
        end_dt = datetime.combine(datetime.today(), new_row['end_time'])
        # Same-day only: duration is 0 if end <= start
        if end_dt > start_dt and row_type != 'gap':
            new_row['shift_duration'] = (end_dt - start_dt).total_seconds() / 3600
        else:
            new_row['shift_duration'] = 0.0

        new_row['counts_for_hours'] = worker_data.get('counts_for_hours', row_type != 'gap')

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
        worker_rows = df[df['PPL'] == ppl_name]
        if len(worker_rows) > 1:
            target_date = _get_staged_target_date() if use_staged else datetime.today().date()
            resolved_df = resolve_overlapping_shifts_df(df, target_date)
            if len(resolved_df) != original_len:
                selection_logger.info(
                    f"Resolved overlapping shifts for {ppl_name} after add: "
                    f"{original_len} -> {len(resolved_df)} rows"
                )
                reindexed = True
            data_dict['working_hours_df'] = resolved_df
            df = data_dict['working_hours_df']

        _recalculate_worker_shift_durations(df, ppl_name)

        backup_dataframe(modality, use_staged=use_staged)
        new_idx = len(data_dict['working_hours_df']) - 1
        return True, {'row_index': new_idx, 'reindexed': reindexed}, None

    except ValueError as e:
        return False, None, f'Invalid time format: {e}'
    except Exception as e:
        return False, None, str(e)


def _replace_worker_schedule(modality: str, worker_name: str, rows: list, use_staged: bool) -> tuple:
    """Replace all schedule rows for a worker with the provided rows."""
    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    try:
        if df is None or df.empty:
            df = pd.DataFrame()
        else:
            df = df[df['PPL'] != worker_name].reset_index(drop=True)

        new_rows = []
        for worker_data in rows:
            row_type = worker_data.get('row_type', 'shift')
            new_row = {
                'PPL': worker_name,
                'start_time': datetime.strptime(worker_data.get('start_time', '07:00'), TIME_FORMAT).time(),
                'end_time': datetime.strptime(worker_data.get('end_time', '15:00'), TIME_FORMAT).time(),
                'Modifier': float(worker_data.get('Modifier', 1.0)),
                'row_type': row_type,
            }

            if not df.empty and 'TIME' in df.columns:
                new_row['TIME'] = f"{new_row['start_time'].strftime(TIME_FORMAT)}-{new_row['end_time'].strftime(TIME_FORMAT)}"

            for skill in SKILL_COLUMNS:
                default_value = -1 if row_type == 'gap' else 0
                new_row[skill] = normalize_skill_value(worker_data.get(skill, default_value))

            tasks = worker_data.get('tasks', [])
            if isinstance(tasks, list):
                new_row['tasks'] = ', '.join(tasks)
            else:
                new_row['tasks'] = tasks or ''

            start_dt = datetime.combine(datetime.today(), new_row['start_time'])
            end_dt = datetime.combine(datetime.today(), new_row['end_time'])
            if end_dt > start_dt and row_type != 'gap':
                new_row['shift_duration'] = (end_dt - start_dt).total_seconds() / 3600
            else:
                new_row['shift_duration'] = 0.0

            new_row['counts_for_hours'] = worker_data.get('counts_for_hours', row_type != 'gap')

            new_rows.append(new_row)

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            df = pd.concat([df, new_df], ignore_index=True)

        if use_staged:
            if df is not None and 'is_manual' not in df.columns:
                df['is_manual'] = False
            if new_rows:
                start_idx = len(df) - len(new_rows)
                df.loc[start_idx:, 'is_manual'] = True

        data_dict['working_hours_df'] = df

        reindexed = False
        if not df.empty:
            worker_shifts = df[df['PPL'] == worker_name]
            if len(worker_shifts) > 1:
                target_date = _get_staged_target_date() if use_staged else datetime.today().date()
                resolved_df = resolve_overlapping_shifts_df(df, target_date)
                if len(resolved_df) != len(df):
                    selection_logger.info(
                        f"Resolved overlapping shifts for {worker_name} after replace: "
                        f"{len(df)} -> {len(resolved_df)} rows"
                    )
                    reindexed = True
                data_dict['working_hours_df'] = resolved_df

        _recalculate_worker_shift_durations(df, worker_name)

        if not use_staged:
            reconcile_live_worker_tracking(modality)

        backup_dataframe(modality, use_staged=use_staged)
        return True, {'reindexed': reindexed}, None

    except ValueError as e:
        return False, None, f'Invalid time format: {e}'
    except Exception as e:
        return False, None, str(e)


def _delete_worker_from_schedule(modality: str, row_index: int, use_staged: bool, verify_ppl: Optional[str] = None) -> tuple:
    """Delete a worker row from the schedule."""
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

        if verify_ppl and str(worker_name) != str(verify_ppl):
            return False, None, 'Row mismatch: Schedule has changed. Please reload.'

        data_dict['working_hours_df'] = df.drop(index=row_index_int).reset_index(drop=True)
        _recalculate_worker_shift_durations(data_dict['working_hours_df'], worker_name)

        if not use_staged:
            reconcile_live_worker_tracking(modality)

        backup_dataframe(modality, use_staged=use_staged)
        return True, worker_name, None

    except Exception as e:
        return False, None, str(e)


def _add_gap_to_schedule(
    modality: str,
    row_index: int,
    gap_type: str,
    gap_start: str,
    gap_end: str,
    use_staged: bool,
    gap_counts_for_hours: Optional[bool] = None,
) -> tuple:
    """Add a gap row for a worker."""
    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    if not _validate_row_index(df, row_index):
        return False, None, 'Invalid row index'

    try:
        _ensure_row_type_column(df)
        worker_name = df.loc[row_index, 'PPL']

        gap_start_time = datetime.strptime(gap_start, TIME_FORMAT).time()
        gap_end_time = datetime.strptime(gap_end, TIME_FORMAT).time()

        if gap_start_time >= gap_end_time:
            return False, None, 'Gap start time must be before gap end time'

        normalized_gap_counts = _coerce_bool(gap_counts_for_hours)
        if normalized_gap_counts is None:
            normalized_gap_counts = False

        gap_row = {
            'PPL': worker_name,
            'start_time': gap_start_time,
            'end_time': gap_end_time,
            'Modifier': 1.0,
            'tasks': gap_type,
            'counts_for_hours': normalized_gap_counts,
            'shift_duration': 0.0,
            'row_type': 'gap',
        }
        for skill in SKILL_COLUMNS:
            gap_row[skill] = -1

        df = pd.concat([df, pd.DataFrame([gap_row])], ignore_index=True)
        if use_staged:
            if 'is_manual' not in df.columns:
                df['is_manual'] = False
            df.at[len(df) - 1, 'is_manual'] = True

        data_dict['working_hours_df'] = df
        _recalculate_worker_shift_durations(df, worker_name)
        backup_dataframe(modality, use_staged=use_staged)
        log_prefix = "STAGED: " if use_staged else ""
        selection_logger.info(f"{log_prefix}Added gap ({gap_type}) for {worker_name} {gap_start}-{gap_end}")
        return True, 'gap_added', None

    except ValueError as e:
        return False, None, f'Invalid time format: {e}'
    except Exception as e:
        return False, None, str(e)


def _remove_gap_from_schedule(
    modality: str,
    row_index: int,
    gap_index: Optional[int],
    use_staged: bool,
    gap_match: Optional[dict] = None,
) -> tuple:
    """Remove a gap row from a worker's schedule."""
    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    if not _validate_row_index(df, row_index):
        return False, None, 'Invalid row index'

    try:
        _ensure_row_type_column(df)
        worker_name = df.loc[row_index, 'PPL']

        if not gap_match:
            return False, None, 'Gap match criteria required'

        match_start = gap_match.get('start')
        match_end = gap_match.get('end')
        match_activity = gap_match.get('activity')

        if not match_start or not match_end:
            return False, None, 'Gap start and end are required'

        start_time = datetime.strptime(match_start, TIME_FORMAT).time()
        end_time = datetime.strptime(match_end, TIME_FORMAT).time()

        gap_candidates = df[
            (df['PPL'] == worker_name) &
            (df['row_type'] == 'gap') &
            (df['start_time'] == start_time) &
            (df['end_time'] == end_time)
        ]

        if match_activity:
            gap_candidates = gap_candidates[gap_candidates['tasks'] == match_activity]

        if gap_candidates.empty:
            return False, None, 'Gap not found for removal'

        gap_row_idx = gap_candidates.index[0]
        removed_gap = df.loc[gap_row_idx]
        df = df.drop(index=gap_row_idx).reset_index(drop=True)
        data_dict['working_hours_df'] = df
        _recalculate_worker_shift_durations(df, worker_name)

        if use_staged and 'is_manual' in df.columns:
            df.loc[df['PPL'] == worker_name, 'is_manual'] = True

        backup_dataframe(modality, use_staged=use_staged)
        log_prefix = "STAGED: " if use_staged else ""
        selection_logger.info(
            f"{log_prefix}Removed gap [{removed_gap.get('tasks', 'unknown')}] "
            f"({match_start}-{match_end}) for {worker_name}"
        )
        return True, 'gap_removed', None

    except Exception as e:
        return False, None, str(e)


def _update_gap_in_schedule(
    modality: str,
    row_index: int,
    gap_index: Optional[int],
    new_start: Optional[str],
    new_end: Optional[str],
    new_activity: Optional[str],
    use_staged: bool,
    new_counts_for_hours: Optional[bool] = None,
    gap_match: Optional[dict] = None,
) -> tuple:
    """Update a gap row in a worker's schedule."""
    data_dict = _get_schedule_data_dict(modality, use_staged)
    df = data_dict['working_hours_df']

    if not _validate_row_index(df, row_index):
        return False, None, 'Invalid row index'

    try:
        _ensure_row_type_column(df)
        worker_name = df.loc[row_index, 'PPL']

        if not gap_match:
            return False, None, 'Gap match criteria required'

        match_start = gap_match.get('start')
        match_end = gap_match.get('end')
        match_activity = gap_match.get('activity')

        if not match_start or not match_end:
            return False, None, 'Gap start and end are required'

        start_time = datetime.strptime(match_start, TIME_FORMAT).time()
        end_time = datetime.strptime(match_end, TIME_FORMAT).time()

        gap_candidates = df[
            (df['PPL'] == worker_name) &
            (df['row_type'] == 'gap') &
            (df['start_time'] == start_time) &
            (df['end_time'] == end_time)
        ]
        if match_activity:
            gap_candidates = gap_candidates[gap_candidates['tasks'] == match_activity]
        if gap_candidates.empty:
            return False, None, 'Gap not found for update'

        gap_row_idx = gap_candidates.index[0]

        if new_start is not None:
            df.at[gap_row_idx, 'start_time'] = datetime.strptime(new_start, TIME_FORMAT).time()
        if new_end is not None:
            df.at[gap_row_idx, 'end_time'] = datetime.strptime(new_end, TIME_FORMAT).time()
        if new_activity is not None:
            df.at[gap_row_idx, 'tasks'] = new_activity
        normalized_gap_counts = _coerce_bool(new_counts_for_hours)
        if normalized_gap_counts is not None:
            df.at[gap_row_idx, 'counts_for_hours'] = normalized_gap_counts

        if use_staged and 'is_manual' in df.columns:
            df.at[gap_row_idx, 'is_manual'] = True

        _recalculate_worker_shift_durations(df, worker_name)
        backup_dataframe(modality, use_staged=use_staged)
        log_prefix = "STAGED: " if use_staged else ""
        selection_logger.info(
            f"{log_prefix}Updated gap ({match_start}-{match_end}) for {worker_name}"
        )
        return True, 'gap_updated', None

    except ValueError as e:
        return False, None, f'Invalid time format: {e}'
    except Exception as e:
        return False, None, str(e)
