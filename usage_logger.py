"""
Usage logging for skill-modality combination tracking.

Tracks daily usage statistics for each skill-modality combination to monitor
tool usage patterns and compare against actual work entries from other data sources.
"""

import csv
import logging
import os
from datetime import datetime, date, time
from pathlib import Path
from typing import Dict, Tuple
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

# Directory for usage statistics CSV files
USAGE_STATS_DIR = Path("logs/usage_stats")
USAGE_STATS_DIR.mkdir(parents=True, exist_ok=True)

# Daily usage tracking: {(skill, modality): count}
_daily_usage: Dict[Tuple[str, str], int] = defaultdict(int)
_current_date: date = date.today()
_lock = threading.Lock()


def record_skill_modality_usage(skill: str, modality: str) -> None:
    """
    Record a single usage of a skill-modality combination.

    Args:
        skill: The skill name (e.g., 'Notfall', 'Privat', 'MSK')
        modality: The modality name (e.g., 'ct', 'mr', 'xray', 'mammo')
    """
    global _current_date

    with _lock:
        today = date.today()

        # Check if we need to export and reset for a new day
        if today != _current_date:
            logger.info(f"Date changed from {_current_date} to {today}, exporting previous day's data")
            _export_and_reset(export_date=_current_date)
            _current_date = today

        # Record the usage
        key = (skill, modality)
        _daily_usage[key] += 1

        logger.debug(f"Recorded usage: skill={skill}, modality={modality}, daily_count={_daily_usage[key]}")


def _export_and_reset(export_date: date = None) -> None:
    """
    Export current usage data to CSV and reset counters.

    Args:
        export_date: Date to use for the export filename (defaults to current_date)
    """
    global _daily_usage

    if export_date is None:
        export_date = _current_date

    if not _daily_usage:
        logger.info(f"No usage data to export for {export_date}")
        return

    # Export to CSV
    csv_path = USAGE_STATS_DIR / f"usage_stats_{export_date.strftime('%Y-%m-%d')}.csv"

    try:
        # Check if file exists to determine if we need headers
        file_exists = csv_path.exists()

        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header if new file
            if not file_exists:
                writer.writerow(['date', 'skill', 'modality', 'count', 'timestamp'])

            # Write data rows
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for (skill, modality), count in sorted(_daily_usage.items()):
                writer.writerow([
                    export_date.strftime('%Y-%m-%d'),
                    skill,
                    modality,
                    count,
                    timestamp
                ])

        logger.info(f"Exported {len(_daily_usage)} skill-modality usage records to {csv_path}")

        # Reset counters
        _daily_usage.clear()
        logger.info("Usage counters reset for new day")

    except Exception as e:
        logger.error(f"Failed to export usage statistics: {e}", exc_info=True)


def export_current_usage() -> Path:
    """
    Manually trigger export of current usage data without resetting.
    Useful for end-of-day exports or manual backups.

    Returns:
        Path to the exported CSV file
    """
    with _lock:
        if not _daily_usage:
            logger.info("No usage data to export")
            return None

        csv_path = USAGE_STATS_DIR / f"usage_stats_{_current_date.strftime('%Y-%m-%d')}.csv"

        try:
            # Always append to existing file
            file_exists = csv_path.exists()

            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write header if new file
                if not file_exists:
                    writer.writerow(['date', 'skill', 'modality', 'count', 'timestamp'])

                # Write data rows
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for (skill, modality), count in sorted(_daily_usage.items()):
                    writer.writerow([
                        _current_date.strftime('%Y-%m-%d'),
                        skill,
                        modality,
                        count,
                        timestamp
                    ])

            logger.info(f"Exported {len(_daily_usage)} skill-modality usage records to {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"Failed to export usage statistics: {e}", exc_info=True)
            return None


def reset_daily_usage() -> None:
    """
    Reset daily usage counters without exporting.
    Use with caution - typically you want export_and_reset() instead.
    """
    global _daily_usage

    with _lock:
        count = len(_daily_usage)
        _daily_usage.clear()
        logger.info(f"Reset {count} usage counter(s)")


def get_current_usage_stats() -> Dict[Tuple[str, str], int]:
    """
    Get current usage statistics without modifying them.

    Returns:
        Dictionary of {(skill, modality): count}
    """
    with _lock:
        return dict(_daily_usage)


def check_and_export_at_scheduled_time() -> bool:
    """
    Check if it's time for the scheduled export (7:30 AM) and export if needed.
    Should be called periodically (e.g., with each assignment request).

    Returns:
        True if export was triggered, False otherwise
    """
    global _current_date

    now = datetime.now()
    current_time = now.time()
    today = now.date()

    # Check if we've crossed 7:30 AM
    scheduled_time = time(7, 30)

    with _lock:
        # If it's a new day and we're past 7:30 AM, or if it's past 7:30 and we haven't exported yet
        if today > _current_date:
            # New day detected, export previous day's data
            logger.info(f"New day detected, exporting data from {_current_date}")
            _export_and_reset(export_date=_current_date)
            _current_date = today
            return True
        elif today == _current_date and current_time >= scheduled_time:
            # Same day, check if we need a scheduled export
            # This is primarily for consistency, main export happens at date change
            pass

    return False


def get_usage_csv_path(target_date: date = None) -> Path:
    """
    Get the path to the usage stats CSV file for a specific date.

    Args:
        target_date: Date to get CSV path for (defaults to today)

    Returns:
        Path object for the CSV file
    """
    if target_date is None:
        target_date = _current_date

    return USAGE_STATS_DIR / f"usage_stats_{target_date.strftime('%Y-%m-%d')}.csv"
