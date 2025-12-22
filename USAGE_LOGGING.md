# Skill-Modality Usage Logging

## Overview

The usage logging system tracks how often each skill-modality combination is used in the RadIMO Cortex application. This data is tracked per work unit (combinations of entries per day) rather than per user, allowing you to monitor tool usage patterns and compare against actual work entries from other data sources.

## Features

- **Automatic Tracking**: Every assignment request automatically logs the skill-modality combination used
- **Daily Aggregation**: Usage is tracked per day with automatic reset and export
- **CSV Export**: Daily statistics are exported to CSV files for easy analysis
- **Scheduled Export**: Automatic export at 7:30 AM daily (or when the first assignment after that time occurs)
- **API Access**: RESTful API endpoints for viewing stats and manual export

## How It Works

### Automatic Logging

When a worker is assigned via the API endpoints:
- `GET /api/<modality>/<role>`
- `GET /api/<modality>/<role>/strict`

The system automatically:
1. Records the skill-modality combination used (e.g., `Notfall + ct`)
2. Increments the daily counter for that combination
3. Checks if it's time for the daily export (7:30 AM)

### Data Structure

The system tracks usage as a simple counter per skill-modality combination:

```
(skill, modality) → count
```

Example:
```
('Notfall', 'ct') → 15
('Privat', 'ct') → 8
('MSK', 'mr') → 12
```

### CSV Export Format

Usage statistics are exported to CSV files in the `logs/usage_stats/` directory.

**Filename Format**: `usage_stats_YYYY-MM-DD.csv`

**CSV Columns**:
- `date`: Date of the usage (YYYY-MM-DD)
- `skill`: Skill name (e.g., Notfall, Privat, MSK)
- `modality`: Modality name (e.g., ct, mr, xray, mammo)
- `count`: Number of times this combination was used
- `timestamp`: When the data was exported (YYYY-MM-DD HH:MM:SS)

**Example**:
```csv
date,skill,modality,count,timestamp
2025-12-22,Notfall,ct,15,2025-12-22 23:59:59
2025-12-22,Privat,ct,8,2025-12-22 23:59:59
2025-12-22,MSK,mr,12,2025-12-22 23:59:59
2025-12-22,Cardvask,ct,5,2025-12-22 23:59:59
```

### Daily Reset

The system automatically exports and resets counters when:
1. **Date Changes**: When the first assignment request occurs on a new day
2. **Scheduled Time**: At or after 7:30 AM (checked with each assignment)

The export preserves the previous day's data to a CSV file before resetting.

## API Endpoints

All endpoints require authentication (via the `@requires_auth` decorator).

### Get Current Usage Statistics

```
GET /api/usage-stats/current
```

Returns the current day's usage statistics in JSON format.

**Response Example**:
```json
{
  "date": "2025-12-22",
  "total_combinations": 8,
  "total_usages": 45,
  "stats": [
    {
      "skill": "Notfall",
      "modality": "ct",
      "count": 15
    },
    {
      "skill": "Privat",
      "modality": "ct",
      "count": 8
    },
    ...
  ]
}
```

### Manual Export

```
POST /api/usage-stats/export
```

Manually triggers an export of current usage statistics to CSV without resetting counters.

**Response Example**:
```json
{
  "success": true,
  "message": "Usage statistics exported successfully",
  "file_path": "logs/usage_stats/usage_stats_2025-12-22.csv",
  "date": "2025-12-22"
}
```

### Reset Statistics

```
POST /api/usage-stats/reset
```

Resets the current usage counters without exporting (use with caution).

**Response Example**:
```json
{
  "success": true,
  "message": "Usage statistics reset successfully"
}
```

### List CSV Files

```
GET /api/usage-stats/files
```

Lists all available usage statistics CSV files.

**Response Example**:
```json
{
  "success": true,
  "total_files": 30,
  "files": [
    {
      "filename": "usage_stats_2025-12-22.csv",
      "date": "2025-12-22",
      "path": "logs/usage_stats/usage_stats_2025-12-22.csv",
      "size_bytes": 1024
    },
    ...
  ]
}
```

## Use Cases

### Monitor Tool Usage vs Actual Work

Compare the daily CSV exports with your actual work entry data:

1. Export the usage statistics CSV
2. Load your work entry data from your external source
3. Join/merge the data on `(date, skill, modality)`
4. Calculate the ratio: `tool_clicks / actual_work_entries`

This helps you understand:
- Which skill-modality combinations are most frequently used
- Whether the tool is being used for all work or only specific cases
- Usage patterns over time

### Track Usage Trends

Analyze the historical CSV files to identify:
- Peak usage times/days
- Seasonal variations
- Changes in workflow patterns
- Most/least used skill-modality combinations

### Capacity Planning

Use the usage data to:
- Identify which skill-modality combinations need more staffing
- Optimize worker schedules based on actual demand
- Predict future resource needs

## File Locations

- **CSV Files**: `logs/usage_stats/usage_stats_YYYY-MM-DD.csv`
- **Module**: `usage_logger.py`
- **Integration**: `routes.py` (lines 1006-1009, 1041-1138)

## Configuration

No additional configuration is required. The system automatically:
- Creates the `logs/usage_stats/` directory if it doesn't exist
- Handles file naming and rotation
- Manages daily reset timing

## Technical Details

### Thread Safety

The usage logger uses a threading lock to ensure thread-safe operations when:
- Recording usage
- Exporting data
- Resetting counters

### Data Persistence

Current usage data is stored in memory only. Daily exports persist to CSV files. If the application restarts during the day, current day's data will be lost (not exported). To prevent this, you can:
1. Set up automatic regular exports via cron
2. Call the manual export endpoint before restart
3. Implement automatic export on application shutdown (future enhancement)

### Performance Impact

The logging system is designed to be lightweight:
- In-memory counter increments (O(1) operation)
- Daily export happens once per day
- No database queries or external API calls
- Minimal overhead per assignment request

## Troubleshooting

### No CSV Files Generated

**Issue**: No CSV files appear in `logs/usage_stats/`

**Solutions**:
- Check that assignments are being made (usage is only recorded when workers are assigned)
- Verify the `logs/usage_stats/` directory exists and is writable
- Check the application logs for export errors

### Missing Data

**Issue**: Some usage data seems to be missing

**Solutions**:
- Check if the application was restarted mid-day (current data is lost on restart)
- Verify that the date change logic is working correctly
- Check the timestamp in the CSV to see when export occurred

### Duplicate Entries

**Issue**: Same date appears multiple times in CSV

**Solutions**:
- This is expected behavior - the CSV is appended to on each export
- Use the `timestamp` column to identify the latest export
- When analyzing, group by `(date, skill, modality)` and sum the counts

## Future Enhancements

Potential improvements to consider:
1. **Persistence**: Save current usage to JSON/database for crash recovery
2. **Scheduled Export**: Add dedicated scheduler (e.g., APScheduler) for precise 7:30 AM export
3. **Web Dashboard**: Add UI to view usage statistics in the admin panel
4. **Alerts**: Send notifications when usage patterns are unusual
5. **Retention Policy**: Automatically archive/delete old CSV files
6. **Analytics**: Built-in analysis tools for common queries
