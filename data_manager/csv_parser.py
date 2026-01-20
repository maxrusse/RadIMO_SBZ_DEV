"""
CSV parser module for medweb CSV transformation.

This module handles:
- Medweb CSV parsing and conversion to modality-specific DataFrames
- 4-pass algorithm: collect shifts, create unavailable entries, apply gaps, resolve overlaps
- Skill overrides and time range computation
- Gap handling (standalone and embedded)
"""
import json
from datetime import datetime, time, date, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable

import pandas as pd

from config import (
    allowed_modalities,
    SKILL_COLUMNS,
    selection_logger,
)
from lib.utils import (
    TIME_FORMAT,
    get_weekday_name_german,
)
from data_manager.worker_management import (
    get_canonical_worker_id,
    get_merged_worker_roster,
    get_worker_skill_mod_combinations,
    apply_skill_overrides,
    extract_modalities_from_skill_overrides,
)
from data_manager.schedule_crud import resolve_overlapping_shifts


DEFAULT_SHIFT_RANGE = (time(7, 0), time(15, 0))


def _default_shift_ranges() -> List[Tuple[time, time]]:
    return [DEFAULT_SHIFT_RANGE]


def _select_day_times(
    times_config: Dict[str, Any],
    weekday_name: str,
    *,
    friday_alias: bool = False,
) -> Optional[Any]:
    if weekday_name in times_config:
        return times_config[weekday_name]
    if friday_alias and weekday_name == 'Freitag' and 'friday' in times_config:
        return times_config['friday']
    if 'default' in times_config:
        return times_config['default']
    return None


def _normalize_time_ranges_input(day_times: Any) -> Optional[List[str]]:
    if isinstance(day_times, str):
        return [day_times]
    if isinstance(day_times, list):
        return day_times
    return None


def _parse_time_ranges(
    time_ranges: Iterable[Any],
    *,
    log_label: str,
) -> List[Tuple[time, time]]:
    parsed_ranges: List[Tuple[time, time]] = []
    for time_range_str in time_ranges:
        if not isinstance(time_range_str, str):
            selection_logger.warning(
                f"Could not parse {log_label} time range '{time_range_str}': expected string"
            )
            continue
        try:
            start_str, end_str = time_range_str.split('-')
            start_time = datetime.strptime(start_str.strip(), TIME_FORMAT).time()
            end_time = datetime.strptime(end_str.strip(), TIME_FORMAT).time()
            parsed_ranges.append((start_time, end_time))
        except ValueError as exc:
            selection_logger.warning(
                f"Could not parse {log_label} time range '{time_range_str}': {exc}"
            )
            continue
    return parsed_ranges


def match_mapping_rule(activity_desc: str, rules: List[dict]) -> Optional[dict]:
    """Match activity description against mapping rules."""
    if not activity_desc:
        return None
    activity_lower = activity_desc.lower()
    for rule in rules:
        match_str = rule.get('match', '')
        if match_str.lower() in activity_lower:
            return rule
    return None


def compute_time_ranges(
    row: pd.Series,
    rule: dict,
    target_date: datetime,
    config: dict,
) -> List[Tuple[time, time]]:
    """
    Compute time ranges from rule's inline 'times' field.

    Structure supports day-specific times with both single string and array formats:
        times:
            default: "07:00-15:00"              # Single time
            Montag: "08:00-16:00"               # Single time for specific day
            Dienstag:                           # Array format for multiple shifts
                - "07:00-12:00"
                - "14:00-18:00"
            Freitag: "07:00-13:00"
    """
    times_config = rule.get('times', {})

    if not times_config:
        # No times specified - use default
        return _default_shift_ranges()

    # Get German weekday name for day-specific lookup
    weekday_name = get_weekday_name_german(target_date)

    # Check for day-specific time first, then 'friday' alias, then default
    day_times = _select_day_times(times_config, weekday_name, friday_alias=True)
    if day_times is None:
        return _default_shift_ranges()

    # Handle both single string and array formats (aligned with parse_gap_times)
    time_ranges_str = _normalize_time_ranges_input(day_times)
    if time_ranges_str is None:
        return _default_shift_ranges()

    time_ranges = _parse_time_ranges(time_ranges_str, log_label="shift")

    # Return default if no valid time ranges were parsed
    if not time_ranges:
        return _default_shift_ranges()

    return time_ranges


def parse_gap_times(times_config: dict, weekday_name: str) -> List[Tuple[time, time]]:
    """
    Parse gap times for a specific weekday.

    Uses unified 'times' field (same as shifts).
    Supports both single string and array formats:
        times:
            Montag: "10:00-11:00"              # Single time
            Dienstag:                          # Array format
                - "10:00-11:00"
                - "14:00-15:00"
            default: "09:00-10:00"             # Optional default

    Returns list of (start_time, end_time) tuples.
    """
    if not times_config:
        return []

    # Check for day-specific times first, then default
    day_times = _select_day_times(times_config, weekday_name)
    if day_times is None:
        return []

    time_ranges = _normalize_time_ranges_input(day_times)
    if time_ranges is None:
        return []

    return _parse_time_ranges(time_ranges, log_label="gap")


def build_ppl_from_row(row: pd.Series, cols: Optional[dict] = None) -> str:
    """Build PPL string from CSV row."""
    name_col = cols.get('employee_name', 'Name des Mitarbeiters') if cols else 'Name des Mitarbeiters'
    code_col = cols.get('employee_code', 'Code des Mitarbeiters') if cols else 'Code des Mitarbeiters'
    name = str(row.get(name_col, 'Unknown'))
    code = str(row.get(code_col, 'UNK'))
    return f"{name} ({code})"


def apply_exclusions_to_shifts(work_shifts: List[dict], exclusions: List[dict], target_date: date) -> List[dict]:
    """Apply exclusions (gaps) to shifts. Same-day operations only.

    NEW MODEL (no row splitting):
    - Gaps are stored as child entities in the shift's 'gaps' JSON array
    - Shift times are preserved (no splitting into segments)
    - shift_duration reflects effective working time (total minus gap durations)
    - Full-shift gaps set counts_for_hours=False
    """
    if not exclusions:
        return work_shifts

    result_shifts = []

    for shift in work_shifts:
        shift_start = shift['start_time']
        shift_end = shift['end_time']

        shift_start_dt = datetime.combine(target_date, shift_start)
        shift_end_dt = datetime.combine(target_date, shift_end)
        # Same-day only: skip invalid shifts where end <= start
        if shift_end_dt <= shift_start_dt:
            continue

        overlapping_exclusions = []
        for excl in exclusions:
            excl_start = excl['start_time']
            excl_end = excl['end_time']

            excl_start_dt = datetime.combine(target_date, excl_start)
            excl_end_dt = datetime.combine(target_date, excl_end)
            # Same-day only: skip invalid exclusions where end <= start
            if excl_end_dt <= excl_start_dt:
                continue

            if excl_start_dt < shift_end_dt and excl_end_dt > shift_start_dt:
                overlapping_exclusions.append((
                    excl_start_dt,
                    excl_end_dt,
                    excl.get('activity', 'Gap'),
                    excl.get('counts_for_hours', False)
                ))

        if not overlapping_exclusions:
            result_shifts.append(shift)
            continue

        overlapping_exclusions.sort(key=lambda x: x[0])

        # Build gaps array (clipped to shift boundaries) with overlap merging
        clipped_exclusions = []
        for excl_start_dt, excl_end_dt, excl_activity, excl_counts_for_hours in overlapping_exclusions:
            # Clip gap to shift boundaries
            clipped_start = max(excl_start_dt, shift_start_dt)
            clipped_end = min(excl_end_dt, shift_end_dt)

            if clipped_end > clipped_start:
                clipped_exclusions.append((clipped_start, clipped_end, excl_activity, excl_counts_for_hours))

        clipped_exclusions.sort(key=lambda x: x[0])

        merged_exclusions = []
        for excl_start_dt, excl_end_dt, excl_activity, excl_counts_for_hours in clipped_exclusions:
            if not merged_exclusions:
                merged_exclusions.append([excl_start_dt, excl_end_dt, excl_activity, excl_counts_for_hours])
                continue

            last_start, last_end, last_activity, last_counts_for_hours = merged_exclusions[-1]
            if excl_start_dt < last_end:
                merged_end = max(last_end, excl_end_dt)
                merged_activity = last_activity if last_activity == excl_activity else 'Gap'
                merged_counts_for_hours = last_counts_for_hours and excl_counts_for_hours
                merged_exclusions[-1] = [last_start, merged_end, merged_activity, merged_counts_for_hours]
            else:
                merged_exclusions.append([excl_start_dt, excl_end_dt, excl_activity, excl_counts_for_hours])

        gap_activities = []
        total_gap_hours = 0.0
        for excl_start_dt, excl_end_dt, excl_activity, excl_counts_for_hours in merged_exclusions:
            gap_activities.append({
                'start': excl_start_dt.time().strftime(TIME_FORMAT),
                'end': excl_end_dt.time().strftime(TIME_FORMAT),
                'activity': excl_activity,
                'counts_for_hours': excl_counts_for_hours
            })
            if not excl_counts_for_hours:
                total_gap_hours += (excl_end_dt - excl_start_dt).total_seconds() / 3600

        # Calculate effective working duration (shift minus gaps)
        total_shift_hours = (shift_end_dt - shift_start_dt).total_seconds() / 3600
        effective_duration = max(0.0, total_shift_hours - total_gap_hours)

        # Keep shift as single row with gaps stored as child entities
        result_shift = {
            **shift,
            'gaps': json.dumps(gap_activities) if gap_activities else None,
            'shift_duration': effective_duration
        }

        # Check if gaps cover entire shift (full-shift gap)
        if effective_duration < 0.1:  # Less than 6 minutes of working time
            result_shift['counts_for_hours'] = False
            result_shift['shift_duration'] = 0.0

        result_shifts.append(result_shift)

    return result_shifts


def build_working_hours_from_medweb(
    csv_path: str,
    target_date: datetime,
    config: dict
) -> Dict[str, pd.DataFrame]:
    """
    Build working hours DataFrames from medweb CSV.

    New unified structure:
    - Shifts have 'times' (day-specific) and 'skill_overrides' (REQUIRED)
    - Modalities are DERIVED from skill_overrides keys
    - Shifts can have embedded 'gaps' for team-specific gaps
    - Standalone gaps support arrays of times per day
    - Day plan building: later shift ends prior, gaps always win
    - Standalone gaps with no shift create "unavailable" entries
    """
    try:
        try:
            medweb_df = pd.read_csv(csv_path, sep=',', encoding='utf-8')
        except UnicodeDecodeError:
            medweb_df = pd.read_csv(csv_path, sep=',', encoding='latin1')
    except Exception:
        try:
            try:
                medweb_df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
            except UnicodeDecodeError:
                medweb_df = pd.read_csv(csv_path, sep=';', encoding='latin1')
        except Exception as e:
            raise ValueError(f"Fehler beim Laden der CSV: {e}")

    def parse_german_date(date_val: Any) -> Optional[date]:
        if pd.isna(date_val):
            return None
        date_str = str(date_val).strip()
        for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        try:
            return pd.to_datetime(date_str, dayfirst=True).date()
        except Exception:
            return None

    vendor_mapping = config.get('medweb_mapping', {})
    cols = vendor_mapping.get('columns', {
        'date': 'Datum',
        'activity': 'Beschreibung der Aktivität',
        'employee_name': 'Name des Mitarbeiters',
        'employee_code': 'Code des Mitarbeiters'
    })

    medweb_df['Datum_parsed'] = medweb_df[cols.get('date', 'Datum')].apply(parse_german_date)
    target_date_obj = target_date.date() if hasattr(target_date, 'date') else target_date

    parsed_dates = medweb_df['Datum_parsed'].dropna().unique().tolist()
    selection_logger.debug(f"CSV dates parsed: {parsed_dates}, target: {target_date_obj}, type: {type(target_date_obj)}")

    day_df = medweb_df[medweb_df['Datum_parsed'] == target_date_obj]

    if day_df.empty:
        selection_logger.warning(f"No rows found for date {target_date_obj}. Available: {parsed_dates}")
        return {}

    mapping_rules = vendor_mapping.get('rules', [])
    worker_roster = get_merged_worker_roster(config)

    selection_logger.debug(f"Found {len(day_df)} rows for target date, {len(mapping_rules)} mapping rules")

    weekday_name = get_weekday_name_german(target_date_obj)

    rows_per_modality = {mod: [] for mod in allowed_modalities}
    exclusions_per_worker: Dict[str, List[dict]] = {}
    workers_with_shifts: set = set()
    unmatched_activities = []

    # FIRST PASS: Collect all shifts and gaps for each worker
    for _, row in day_df.iterrows():
        activity_desc = str(row.get(cols.get('activity', 'Beschreibung der Aktivität'), ''))
        rule = match_mapping_rule(activity_desc, mapping_rules)
        if not rule:
            unmatched_activities.append(activity_desc)
            continue

        ppl_str = build_ppl_from_row(row, cols=cols)
        canonical_id = get_canonical_worker_id(ppl_str)
        rule_type = rule.get('type', 'shift')

        # Handle GAP rules (standalone gaps)
        if rule_type == 'gap':
            # Use 'times' field (unified structure)
            times_config = rule.get('times', {})
            gap_times = parse_gap_times(times_config, weekday_name)

            if not gap_times:
                continue

            hours_counting_config = config.get('balancer', {}).get('hours_counting', {})
            if 'counts_for_hours' in rule:
                counts_for_hours = rule['counts_for_hours']
            else:
                counts_for_hours = hours_counting_config.get('gap_default', False)

            if canonical_id not in exclusions_per_worker:
                exclusions_per_worker[canonical_id] = []

            # Use label if available, otherwise fall back to raw activity
            gap_label = rule.get('label', activity_desc)

            for gap_start, gap_end in gap_times:
                exclusions_per_worker[canonical_id].append({
                    'start_time': gap_start,
                    'end_time': gap_end,
                    'activity': gap_label,
                    'counts_for_hours': counts_for_hours,
                    'ppl_str': ppl_str
                })

                selection_logger.info(
                    f"Time exclusion for {ppl_str} ({weekday_name}): "
                    f"{gap_start.strftime(TIME_FORMAT)}-{gap_end.strftime(TIME_FORMAT)} ({activity_desc})"
                )
            continue

        # Handle SHIFT rules
        if rule_type != 'shift':
            continue

        # Get skill_overrides - REQUIRED for shifts
        skill_overrides = rule.get('skill_overrides', {})

        if not skill_overrides:
            selection_logger.warning(
                f"Shift rule '{rule.get('match', '')}' missing skill_overrides - skipping"
            )
            continue

        # Derive modalities from skill_overrides keys (e.g., MSK_ct -> ct)
        target_modalities = extract_modalities_from_skill_overrides(skill_overrides)
        target_modalities = [m for m in target_modalities if m in allowed_modalities]

        if not target_modalities:
            selection_logger.warning(
                f"Shift rule '{rule.get('match', '')}' has no valid modalities in skill_overrides - skipping"
            )
            continue

        workers_with_shifts.add(canonical_id)

        # Get worker's Skill x Modality combinations from roster (all combinations)
        roster_combinations = get_worker_skill_mod_combinations(canonical_id, worker_roster)

        # Apply skill_overrides (roster -1 always wins, shortcuts are expanded)
        final_combinations = apply_skill_overrides(roster_combinations, skill_overrides)

        time_ranges = compute_time_ranges(row, rule, target_date, config)

        # Handle embedded gaps in shift rule (team-specific gaps)
        embedded_gaps = rule.get('gaps', {})
        embedded_gap_times = parse_gap_times(embedded_gaps, weekday_name)

        if embedded_gap_times:
            hours_counting_config = config.get('balancer', {}).get('hours_counting', {})
            if 'counts_for_hours' in rule:
                counts_for_hours = rule['counts_for_hours']
            else:
                counts_for_hours = hours_counting_config.get('gap_default', False)

            if canonical_id not in exclusions_per_worker:
                exclusions_per_worker[canonical_id] = []

            # Use label if available for embedded gaps
            embedded_gap_label = rule.get('label', activity_desc)

            for gap_start, gap_end in embedded_gap_times:
                exclusions_per_worker[canonical_id].append({
                    'start_time': gap_start,
                    'end_time': gap_end,
                    'activity': f"{embedded_gap_label} (gap)",
                    'counts_for_hours': counts_for_hours,
                    'ppl_str': ppl_str
                })
                selection_logger.info(
                    f"Embedded gap for {ppl_str} ({weekday_name}): "
                    f"{gap_start.strftime(TIME_FORMAT)}-{gap_end.strftime(TIME_FORMAT)} ({embedded_gap_label})"
                )

        for modality in target_modalities:
            # Extract skills for THIS modality from combinations
            modality_skills = {}
            for skill in SKILL_COLUMNS:
                combo_key = f"{skill}_{modality}"
                modality_skills[skill] = final_combinations.get(combo_key, 0)

            for start_time, end_time in time_ranges:
                start_dt = datetime.combine(target_date_obj, start_time)
                end_dt = datetime.combine(target_date_obj, end_time)
                # Same-day only: skip invalid shifts where end <= start
                if end_dt <= start_dt:
                    continue
                duration_hours = (end_dt - start_dt).total_seconds() / 3600

                rule_modifier = rule.get('modifier', 1.0)
                hours_counting_config = config.get('balancer', {}).get('hours_counting', {})
                if 'counts_for_hours' in rule:
                    counts_for_hours = rule['counts_for_hours']
                else:
                    counts_for_hours = hours_counting_config.get('shift_default', True)

                # Use label for task name (shorter, cleaner than raw CSV text)
                task_label = rule.get('label', activity_desc)

                rows_per_modality[modality].append({
                    'PPL': ppl_str,
                    'canonical_id': canonical_id,
                    'start_time': start_time,
                    'end_time': end_time,
                    'shift_duration': duration_hours,
                    'Modifier': rule_modifier,
                    'tasks': task_label,
                    'counts_for_hours': counts_for_hours,
                    **modality_skills
                })

    # SECOND PASS: Create "unavailable" entries for workers with gaps but no shifts
    for canonical_id, exclusions in exclusions_per_worker.items():
        if canonical_id in workers_with_shifts:
            continue  # Will be handled in gap application

        # Worker has only gaps, no shifts -> create "unavailable" entry
        for excl in exclusions:
            ppl_str = excl.get('ppl_str', f'Unknown ({canonical_id})')
            gap_start = excl['start_time']
            gap_end = excl['end_time']
            activity = excl['activity']

            start_dt = datetime.combine(target_date_obj, gap_start)
            end_dt = datetime.combine(target_date_obj, gap_end)
            # Same-day only: skip invalid gaps where end <= start
            if end_dt <= start_dt:
                continue
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            counts_for_hours = excl.get('counts_for_hours', False)
            effective_duration = duration_hours if counts_for_hours else 0.0

            # Create an entry in all modalities (or just first one) with all skills = -1
            unavailable_skills = {skill: -1 for skill in SKILL_COLUMNS}

            # Add to first modality (could be all, but one is enough for visibility)
            first_mod = allowed_modalities[0] if allowed_modalities else 'ct'
            rows_per_modality[first_mod].append({
                'PPL': ppl_str,
                'canonical_id': canonical_id,
                'start_time': gap_start,
                'end_time': gap_end,
                'shift_duration': effective_duration,
                'Modifier': 1.0,
                'tasks': f"[Unavailable] {activity}",
                'counts_for_hours': counts_for_hours,
                'gaps': json.dumps([{
                    'start': gap_start.strftime(TIME_FORMAT),
                    'end': gap_end.strftime(TIME_FORMAT),
                    'activity': activity,
                    'counts_for_hours': counts_for_hours
                }]),
                **unavailable_skills
            })

            selection_logger.info(
                f"Created unavailable entry for {ppl_str} ({weekday_name}): "
                f"{gap_start.strftime(TIME_FORMAT)}-{gap_end.strftime(TIME_FORMAT)} ({activity})"
            )

    # THIRD PASS: Apply gaps to shifts (gaps always win)
    if exclusions_per_worker:
        selection_logger.info(f"Applying time exclusions for {len(exclusions_per_worker)} workers on {weekday_name}")

        for modality in rows_per_modality:
            if not rows_per_modality[modality]:
                continue

            shifts_by_worker: Dict[str, List[dict]] = {}
            for shift in rows_per_modality[modality]:
                worker_id = shift['canonical_id']
                if worker_id not in shifts_by_worker:
                    shifts_by_worker[worker_id] = []
                shifts_by_worker[worker_id].append(shift)

            new_shifts = []
            for worker_id, worker_shifts in shifts_by_worker.items():
                worker_exclusions = exclusions_per_worker.get(worker_id, [])
                if worker_exclusions and worker_id in workers_with_shifts:
                    worker_shifts = apply_exclusions_to_shifts(
                        worker_shifts,
                        worker_exclusions,
                        target_date_obj
                    )

                    # NOTE: Gap overwrite edge case - if a shift already has gaps from a
                    # previous operation (e.g., duplicate worker entries), this will overwrite
                    # them. All exclusions for a worker are combined into a single gaps_json.
                    gaps_json = json.dumps([{
                        'start': excl['start_time'].strftime(TIME_FORMAT),
                        'end': excl['end_time'].strftime(TIME_FORMAT),
                        'activity': excl['activity']
                    } for excl in worker_exclusions])

                    for shift in worker_shifts:
                        shift['gaps'] = gaps_json

                new_shifts.extend(worker_shifts)

            rows_per_modality[modality] = new_shifts

    if unmatched_activities:
        selection_logger.debug(f"Unmatched activities: {set(unmatched_activities)}")

    # FOURTH PASS: Resolve overlapping shifts (later shift ends prior)
    for modality in rows_per_modality:
        if rows_per_modality[modality]:
            original_count = len(rows_per_modality[modality])
            rows_per_modality[modality] = resolve_overlapping_shifts(
                rows_per_modality[modality], target_date_obj
            )
            resolved_count = len(rows_per_modality[modality])
            if original_count != resolved_count:
                selection_logger.info(
                    f"Resolved overlapping shifts for {modality}: {original_count} -> {resolved_count} shifts"
                )

    result = {}
    for modality, rows in rows_per_modality.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if 'canonical_id' in df.columns:
            df = df.drop(columns=['canonical_id'])
        result[modality] = df

    selection_logger.info(f"Loaded {sum(len(df) for df in result.values())} workers across {list(result.keys())}")
    return result
