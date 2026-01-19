# Standard library imports
from datetime import datetime
from typing import Optional

# Third-party imports
import pandas as pd

# Local imports
from config import (
    BALANCER_SETTINGS,
    SKILL_COLUMNS,
    EXCLUDE_SKILLS,
    ROLE_MAP,
    default_modality,
    selection_logger,
    get_skill_modality_weight,
    coerce_float
)
from lib.utils import (
    compute_shift_window,
    is_now_in_shift,
    skill_value_to_numeric,
    is_weighted_skill,
)
from data_manager import (
    get_canonical_worker_id,
    get_roster_modifier,
    get_global_modifier,
    global_worker_data,
    modality_data,
)
from state_manager import get_state

# -----------------------------------------------------------
# Helper functions to compute global totals across modalities
# -----------------------------------------------------------
def get_global_weighted_count(canonical_id: str) -> float:
    """Get single global weighted count for a worker (consolidated across all modalities)."""
    return global_worker_data['weighted_counts'].get(canonical_id, 0.0)


def get_modality_weighted_count(canonical_id: str, modality: str) -> float:
    """
    Compute weighted count for a worker in a specific modality.

    Calculated from assignments_per_mod using skill×modality weights.
    This replaces the broken WeightedCounts structure that was never populated.
    """
    assignments = global_worker_data['assignments_per_mod'].get(modality, {}).get(canonical_id, {})
    if not assignments:
        return 0.0

    total_weight = 0.0
    for skill in SKILL_COLUMNS:
        count = assignments.get(skill, 0)
        if count > 0:
            weight = get_skill_modality_weight(skill, modality)
            total_weight += count * weight
    return total_weight


def get_global_assignments(canonical_id: str) -> dict[str, int]:
    """Get aggregated assignment counts for a worker across all modalities."""
    totals = {skill: 0 for skill in SKILL_COLUMNS}
    totals['total'] = 0
    for mod in modality_data.keys():
        mod_assignments = global_worker_data['assignments_per_mod'][mod].get(canonical_id, {})
        for skill in SKILL_COLUMNS:
            totals[skill] += mod_assignments.get(skill, 0)
        totals['total'] += mod_assignments.get('total', 0)
    return totals

def _get_or_create_assignments(modality: str, canonical_id: str) -> dict:
    """Get or create assignment tracking dict for a worker in a modality.

    Note: modality must be validated before calling this function.
    All modalities are pre-initialized in global_worker_data at module load.
    """
    assignments = global_worker_data['assignments_per_mod'][modality]
    if canonical_id not in assignments:
        assignments[canonical_id] = {skill: 0 for skill in SKILL_COLUMNS}
        assignments[canonical_id]['total'] = 0
    return assignments[canonical_id]

def update_global_assignment(person: str, role: str, modality: str, is_weighted: bool = False) -> str:
    """
    Record a worker assignment and update global weighted counts.

    IMPORTANT: This function modifies global state and must be called while holding
    the global lock. The caller is responsible for calling save_state() after
    releasing the lock to persist changes (prevents blocking I/O under lock).

    Args:
        person: Worker name (PPL field)
        role: Skill/role assigned (e.g., 'Notfall', 'MSK')
        modality: Modality assigned (e.g., 'ct', 'mr')
        is_weighted: If True (skill='w'), also apply worker's 'w' modifier.
                     If False (skill=1 or 0), only apply global_modifier.

    Returns:
        Canonical worker ID
    """
    canonical_id = get_canonical_worker_id(person)

    # Always apply global_modifier to ALL assignments (0, w, 1)
    # Higher global_modifier = less work (e.g., 1.5 = ~33% less work)
    global_modifier = get_global_modifier(canonical_id)
    global_modifier = global_modifier if global_modifier > 0 else 1.0

    # For weighted ('w') assignments, also apply the 'w' modifier
    # skill=1 (regular specialist) and skill=0 (generalist) only use global_modifier
    if is_weighted:
        # Priority: shift modifier (if != 1.0) > roster modifier > default_w_modifier
        # Shift modifier of 1.0 is treated as "not explicitly set"
        shift_modifier = modality_data[modality]['worker_modifiers'].get(person, 1.0)
        shift_modifier = coerce_float(shift_modifier, 1.0)

        if shift_modifier != 1.0:
            # Shift explicitly set a non-default modifier
            w_modifier = shift_modifier
        else:
            # Fallback to roster modifier (for trainees without shift-specific modifier)
            w_modifier = get_roster_modifier(canonical_id)

        w_modifier = w_modifier if w_modifier > 0 else 1.0
    else:
        w_modifier = 1.0

    # Combined modifier: global_modifier applies to all, w_modifier only for 'w'
    combined_modifier = global_modifier * w_modifier
    weight = get_skill_modality_weight(role, modality) * (1.0 / combined_modifier)

    # Update single global weighted count (consolidated across all modalities)
    global_worker_data['weighted_counts'][canonical_id] = \
        global_worker_data['weighted_counts'].get(canonical_id, 0.0) + weight

    assignments = _get_or_create_assignments(modality, canonical_id)
    assignments[role] += 1
    assignments['total'] += 1

    # NOTE: save_state() is NOT called here to avoid blocking I/O under lock.
    # The caller must call save_state() after releasing the lock.

    return canonical_id

def calculate_work_hours_now(current_dt: datetime, modality: str) -> dict[str, float]:
    """
    Calculate cumulative work hours for all workers up to current_dt.

    Uses TTL cache (~1 minute) to avoid recalculating on every assignment.
    Cache key is based on modality and minute-truncated timestamp.
    """
    # Round to minute for cache key (cache valid for same minute)
    cache_minute = current_dt.replace(second=0, microsecond=0)
    cache_key = f"work_hours:{modality}:{cache_minute.isoformat()}"

    state = get_state()
    cached = state.work_hours_cache.get(cache_key)
    if cached is not None:
        return cached

    d = modality_data[modality]
    if d['working_hours_df'] is None:
        return {}

    df = d['working_hours_df']

    # Filter without copy - use boolean indexing on original
    if 'counts_for_hours' in df.columns:
        mask = df['counts_for_hours'].fillna(True).astype(bool)
        df_filtered = df.loc[mask]
    else:
        df_filtered = df

    if df_filtered.empty:
        return {}

    def _calc(row):
        start_dt, end_dt = compute_shift_window(row['start_time'], row['end_time'], current_dt)
        if current_dt < start_dt:
            return 0.0
        if current_dt >= end_dt:
            return (end_dt - start_dt).total_seconds() / 3600.0
        return (current_dt - start_dt).total_seconds() / 3600.0

    # Calculate hours directly - avoid adding column to original DataFrame
    work_hours = df_filtered.apply(_calc, axis=1)

    hours_by_canonical = {}
    all_workers = df_filtered['PPL'].dropna().unique().tolist()
    for worker in all_workers:
        canonical_id = get_canonical_worker_id(worker)
        hours_by_canonical[canonical_id] = 0.0

    # Aggregate by PPL using calculated series
    for idx, hours in work_hours.items():
        worker = df_filtered.loc[idx, 'PPL']
        if pd.notna(worker):
            canonical_id = get_canonical_worker_id(worker)
            hours_by_canonical[canonical_id] = hours_by_canonical.get(canonical_id, 0) + hours

    # Cache the result
    state.work_hours_cache.set(cache_key, hours_by_canonical)

    return hours_by_canonical


def calculate_global_work_hours_now(current_dt: datetime) -> dict[str, float]:
    """
    Calculate cumulative work hours for all workers across ALL modalities up to current_dt.

    This aggregates hours from all modalities to provide a consistent basis for
    comparing against global weighted counts. Uses caching via calculate_work_hours_now.

    Returns dict: {canonical_id: total_hours_across_all_modalities}
    """
    global_hours = {}

    for mod in modality_data.keys():
        mod_hours = calculate_work_hours_now(current_dt, mod)
        for canonical_id, hours in mod_hours.items():
            global_hours[canonical_id] = global_hours.get(canonical_id, 0.0) + hours

    return global_hours


def _filter_active_rows(df: Optional[pd.DataFrame], current_dt: datetime) -> Optional[pd.DataFrame]:
    """Return only rows active at ``current_dt`` (same-day shifts only).

    Note: Skill values are NOT converted to numeric here to preserve 'w' marker.
    Use skill_value_to_numeric() for comparisons, is_weighted_skill() to check for 'w'.

    Returns a view (not a copy) for performance. Do not modify the returned DataFrame.
    """
    if df is None or df.empty:
        return df

    active_mask = df.apply(
        lambda row: is_now_in_shift(row['start_time'], row['end_time'], current_dt),
        axis=1
    )
    # Return view without copy - callers only read from this
    return df.loc[active_mask]

def _filter_near_shift_end(df: pd.DataFrame, current_dt: datetime, buffer_minutes: int) -> pd.DataFrame:
    """
    Filter out workers who are within buffer_minutes of their shift end.
    Used to prevent overflow assignments near end of shift.

    Returns a view (not a copy) for performance. Do not modify the returned DataFrame.
    """
    if df is None or df.empty or buffer_minutes <= 0:
        return df

    def is_not_near_shift_end(row):
        start_dt, end_dt = compute_shift_window(row['start_time'], row['end_time'], current_dt)
        minutes_until_end = (end_dt - current_dt).total_seconds() / 60
        return minutes_until_end > buffer_minutes

    mask = df.apply(is_not_near_shift_end, axis=1)
    return df.loc[mask]

def _filter_near_shift_start(df: pd.DataFrame, current_dt: datetime, buffer_minutes: int) -> pd.DataFrame:
    """
    Filter out workers who are within buffer_minutes of their shift start.
    Used to prevent overflow assignments at beginning of shift.

    Returns a view (not a copy) for performance. Do not modify the returned DataFrame.
    """
    if df is None or df.empty or buffer_minutes <= 0:
        return df

    def is_not_near_shift_start(row):
        start_dt, end_dt = compute_shift_window(row['start_time'], row['end_time'], current_dt)
        minutes_since_start = (current_dt - start_dt).total_seconds() / 60
        return minutes_since_start > buffer_minutes

    mask = df.apply(is_not_near_shift_start, axis=1)
    return df.loc[mask]

def _get_effective_assignment_load(
    worker: str,
    column: str,
    modality: str,
    skill_counts: Optional[dict] = None,
) -> float:
    """
    Get effective assignment load for minimum balancer.

    Uses weighted counts consistently to avoid comparing different units.
    Returns max of modality-specific weighted count and global weighted count.
    """
    canonical_id = get_canonical_worker_id(worker)

    # Use weighted counts consistently (both are in weighted units)
    modality_weighted = get_modality_weighted_count(canonical_id, modality)
    global_weighted = get_global_weighted_count(canonical_id)

    return max(modality_weighted, global_weighted)

def _apply_minimum_balancer(filtered_df: pd.DataFrame, column: str, modality: str) -> pd.DataFrame:
    if filtered_df.empty or not BALANCER_SETTINGS.get('enabled', True):
        return filtered_df
    min_required = BALANCER_SETTINGS.get('min_assignments_per_skill', 0)
    if min_required <= 0:
        return filtered_df

    skill_counts = modality_data[modality]['skill_counts'].get(column, {})
    if not skill_counts:
        return filtered_df

    working_hours_df = modality_data[modality].get('working_hours_df')
    if working_hours_df is None or column not in working_hours_df.columns:
        return filtered_df

    any_below_minimum = False
    for worker in skill_counts.keys():
        worker_rows = working_hours_df[working_hours_df['PPL'] == worker]
        if worker_rows.empty:
            continue

        skill_value = skill_value_to_numeric(worker_rows[column].iloc[0])
        if skill_value < 1:
            continue

        count = _get_effective_assignment_load(worker, column, modality, skill_counts)
        if count < min_required:
            any_below_minimum = True
            break

    if not any_below_minimum:
        return filtered_df

    prioritized = filtered_df[
        filtered_df['PPL'].apply(
            lambda worker: _get_effective_assignment_load(worker, column, modality, skill_counts)
            < min_required
        )
    ]

    if prioritized.empty:
        return filtered_df
    return prioritized

def _get_worker_exclusion_based(
    current_dt: datetime,
    role: str,
    modality: str,
    allow_overflow: bool,
):
    """
    Specialist-first assignment with pooled worker overflow.

    Strategy:
    1. Filter workers in requested modality by skill>=0 (excludes skill=-1)
    2. Apply exclusion rules (e.g., notfall_ct team won't get mammo_gyn)
    3. Split into specialists (skill=1/'w') and generalists (skill=0)
    4. Try specialists first, overflow to generalists only if all specialists overloaded
    5. Retry: if exclusions filter out everyone, retry without exclusions (if overflow enabled)
    """
    role_lower = role.lower()
    if role_lower not in ROLE_MAP:
        role_lower = 'normal'
    primary_skill = ROLE_MAP[role_lower]

    # Get exclusion list and overflow settings
    exclude_skills = EXCLUDE_SKILLS.get(primary_skill, [])
    imbalance_threshold_pct = BALANCER_SETTINGS.get('imbalance_threshold_pct', 30)
    shift_start_buffer = BALANCER_SETTINGS.get('disable_overflow_at_shift_start_minutes', 0)
    shift_end_buffer = BALANCER_SETTINGS.get('disable_overflow_at_shift_end_minutes', 0)

    selection_logger.info(
        "Specialist-first routing for skill %s in modality %s: exclude %s=1, imbalance_threshold=%d%%",
        primary_skill,
        modality,
        exclude_skills if exclude_skills else 'none',
        imbalance_threshold_pct,
    )

    # Helper function to try selection with given filters
    def try_selection(apply_exclusions: bool):
        if modality not in modality_data:
            return None

        d = modality_data[modality]
        if d['working_hours_df'] is None:
            return None

        active_df = _filter_active_rows(d['working_hours_df'], current_dt)
        if active_df is None or active_df.empty:
            return None

        if primary_skill not in active_df.columns:
            return None

        # Filter by skill >= 0 (excludes skill=-1), handling 'w' as specialist
        # 'w' is treated as skill=1 for filtering, but preserved for modifier logic
        skill_filtered = active_df[
            active_df[primary_skill].apply(lambda v: skill_value_to_numeric(v) >= 0)
        ]
        if skill_filtered.empty:
            return None

        # Apply exclusion rules if requested
        filtered_workers = skill_filtered
        if apply_exclusions:
            for skill_to_exclude in exclude_skills:
                if skill_to_exclude in filtered_workers.columns:
                    # Exclude workers where skill_to_exclude >= 1 (including 'w')
                    filtered_workers = filtered_workers[
                        filtered_workers[skill_to_exclude].apply(lambda v: skill_value_to_numeric(v) < 1)
                    ]
            if filtered_workers.empty:
                return None

        # Calculate workload ratios using GLOBAL hours (across all modalities)
        # to be consistent with global weighted counts - both are now in the same units
        global_hours_map = calculate_global_work_hours_now(current_dt)

        def weighted_ratio(person):
            canonical_id = get_canonical_worker_id(person)
            # Use global hours to match global weighted counts (consistent units)
            hours_worked = global_hours_map.get(canonical_id, 0.0)
            weighted_count = get_global_weighted_count(canonical_id)
            if hours_worked <= 0:
                return 0.0 if weighted_count <= 0 else float('inf')
            return weighted_count / hours_worked

        # Split into specialists (skill=1 or 'w') and generalists (skill=0)
        # 'w' workers use their personal modifier, skill=1 workers do not
        specialists_df = filtered_workers[
            filtered_workers[primary_skill].apply(lambda v: skill_value_to_numeric(v) == 1)
        ]
        generalists_all = filtered_workers[
            filtered_workers[primary_skill].apply(lambda v: skill_value_to_numeric(v) == 0)
        ]

        # Apply shift start/end buffers ONLY to generalists (overflow pool)
        # Specialists (1, w) handle their own work even at shift boundaries
        # Keep original generalists_all for fallback if no specialists available
        generalists_df = generalists_all
        if not generalists_df.empty:
            if shift_start_buffer > 0:
                generalists_df = _filter_near_shift_start(generalists_df, current_dt, shift_start_buffer)
            if shift_end_buffer > 0:
                generalists_df = _filter_near_shift_end(generalists_df, current_dt, shift_end_buffer)

        # Strategy: Try specialists first, overflow to generalists if needed
        if not specialists_df.empty:
            # Apply minimum balancer to specialists
            balanced_specialists = _apply_minimum_balancer(specialists_df, primary_skill, modality)
            specialists_to_check = balanced_specialists if not balanced_specialists.empty else specialists_df

            specialist_workers = specialists_to_check['PPL'].unique()
            specialist_ratios = {p: weighted_ratio(p) for p in specialist_workers}
            if not specialist_ratios:
                selection_logger.warning(
                    "No specialist ratios computed for skill %s in modality %s",
                    primary_skill,
                    modality,
                )
            else:
                # Check if should overflow to generalists based on imbalance
                overflow_triggered = False
                if not generalists_df.empty and imbalance_threshold_pct > 0:
                    # Calculate min ratios for both pools
                    min_specialist_ratio = min(specialist_ratios.values())

                    generalist_workers = generalists_df['PPL'].unique()
                    generalist_ratios = {p: weighted_ratio(p) for p in generalist_workers}
                    if generalist_ratios:
                        min_generalist_ratio = min(generalist_ratios.values())
                    else:
                        min_generalist_ratio = None

                    # Check if specialists are imbalanced compared to generalists
                    if min_generalist_ratio is not None and min_generalist_ratio < min_specialist_ratio:
                        specialist_avg = sum(specialist_ratios.values()) / len(specialist_ratios)
                        generalist_avg = sum(generalist_ratios.values()) / len(generalist_ratios)
                        imbalance_baseline = max(specialist_avg, generalist_avg)
                        if imbalance_baseline <= 0:
                            imbalance_pct = 0.0
                        else:
                            imbalance_pct = ((min_specialist_ratio - min_generalist_ratio) / imbalance_baseline) * 100
                        if imbalance_pct >= imbalance_threshold_pct:
                            overflow_triggered = True
                            selection_logger.info(
                                "Specialist overflow triggered: specialist_min=%.4f, generalist_min=%.4f, imbalance=%.1f%% >= %d%%",
                                min_specialist_ratio,
                                min_generalist_ratio,
                                imbalance_pct,
                                imbalance_threshold_pct,
                            )

                # If overflow not triggered, use specialist with lowest ratio
                if not overflow_triggered:
                    best_specialist = min(specialist_workers, key=lambda p: specialist_ratios[p])
                    candidate = specialists_to_check[specialists_to_check['PPL'] == best_specialist].iloc[0].copy()
                    candidate['__modality_source'] = modality
                    candidate['__selection_ratio'] = specialist_ratios[best_specialist]
                    # Track if this is a weighted ('w') assignment - affects modifier usage
                    candidate['__is_weighted'] = is_weighted_skill(candidate.get(primary_skill))

                    selection_logger.info(
                        "Selected specialist: person=%s, skill=%s=%s, weighted=%s, ratio=%.4f",
                        candidate.get('PPL', 'unknown'),
                        primary_skill,
                        candidate.get(primary_skill, '?'),
                        candidate['__is_weighted'],
                        specialist_ratios[best_specialist],
                    )

                    return candidate, primary_skill, modality

        # Use generalists if: (1) no specialists, OR (2) overflow triggered
        # If no buffer-filtered generalists but specialists_df is empty, fallback to all generalists
        generalists_to_use = generalists_df
        if generalists_to_use.empty and specialists_df.empty and not generalists_all.empty:
            # No specialists available - ignore shift buffers and use any generalist
            generalists_to_use = generalists_all
            selection_logger.info(
                "No specialists available for skill %s - ignoring shift buffers for generalists",
                primary_skill,
            )

        if not generalists_to_use.empty:
            balanced_generalists = _apply_minimum_balancer(generalists_to_use, primary_skill, modality)
            generalists_to_check = balanced_generalists if not balanced_generalists.empty else generalists_to_use

            generalist_workers = generalists_to_check['PPL'].unique()
            generalist_ratios = {p: weighted_ratio(p) for p in generalist_workers}
            if not generalist_ratios:
                selection_logger.warning(
                    "No generalist ratios computed for skill %s in modality %s",
                    primary_skill,
                    modality,
                )
                return None

            best_generalist = min(generalist_workers, key=lambda p: generalist_ratios[p])
            candidate = generalists_to_check[generalists_to_check['PPL'] == best_generalist].iloc[0].copy()
            candidate['__modality_source'] = modality
            candidate['__selection_ratio'] = generalist_ratios[best_generalist]
            # Generalists (skill=0) never use weighted modifier
            candidate['__is_weighted'] = False

            selection_logger.info(
                "Selected generalist (pooled): person=%s, skill=%s=0, ratio=%.4f",
                candidate.get('PPL', 'unknown'),
                primary_skill,
                generalist_ratios[best_generalist],
            )

            return candidate, primary_skill, modality

        return None

    # Level 1: Try with exclusions
    result = try_selection(apply_exclusions=True)
    if result:
        return result

    # Level 2: Retry without exclusions if overflow enabled
    if not allow_overflow:
        selection_logger.info(
            "No workers available with exclusions for skill %s, overflow disabled",
            primary_skill,
        )
        return None

    selection_logger.info(
        "No workers with exclusions, retrying without exclusion filters",
    )

    result = try_selection(apply_exclusions=False)
    if result:
        return result

    selection_logger.info(
        "No workers available for skill %s in modality %s",
        primary_skill,
        modality,
    )
    return None

def get_next_available_worker(
    current_dt: datetime,
    role='normal',
    modality=default_modality,
    allow_overflow: bool = True,
):
    return _get_worker_exclusion_based(current_dt, role, modality, allow_overflow)
