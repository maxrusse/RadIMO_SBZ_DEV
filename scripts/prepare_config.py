#!/usr/bin/env python3
"""Generate draft vendor_mappings rules from a Medweb CSV.

This helper is intentionally standalone so admins can run it once to bootstrap
`config.yaml` outside the web UI. It scans the activity descriptions in a CSV
and creates a YAML snippet with best-effort guesses for times and skill overrides.
Unknown pieces are marked with TODO-style values so they are easy to fix by hand.

Usage:
    python prepare_config.py --input uploads/master_medweb.csv --output draft.yaml

Notes:
- Only shift-type rules are generated (no gap/exclusion rules).
- Guesses rely on simple keyword heuristics; review the output before use.
- The script never overwrites your live config; it writes a separate YAML file.
- Output uses the NEW vendor_mappings format with embedded times and skill_overrides.
"""

from __future__ import annotations

import argparse
import collections
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import yaml

DEFAULT_OUTPUT = "generated_medweb_mapping.yaml"


def load_existing_config(config_path: Path) -> Dict:
    """Load config.yaml if present to capture skills/modalities."""
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        try:
            return yaml.safe_load(handle) or {}
        except yaml.YAMLError:
            return {}


def extract_skills(config: Dict) -> List[str]:
    """Return ordered skill keys from config, falling back to defaults."""
    skills = list(config.get("skills", {}).keys())
    if skills:
        return skills
    raise SystemExit("No skills found in config.yaml. Define skills before generating mappings.")


def extract_modalities(config: Dict) -> List[str]:
    modalities = list(config.get("modalities", {}).keys())
    if modalities:
        return modalities
    raise SystemExit("No modalities found in config.yaml. Define modalities before generating mappings.")


def guess_times_from_activity(activity: str, day_part: str) -> Tuple[Dict[str, str], str]:
    """Guess shift times based on activity description and day part.

    Returns: (times dict, source)
    """
    normalized = activity.lower()
    day_part_lower = (day_part or "").lower()

    # Default times for common shift patterns
    DEFAULT_EARLY = {"default": "07:00-15:00", "Freitag": "07:00-13:00"}
    DEFAULT_LATE = {"default": "13:00-21:00", "Freitag": "13:00-19:00"}
    DEFAULT_NIGHT = {"default": "21:00-07:00"}

    # Check for explicit shift indicators
    if "spät" in normalized or "spaet" in normalized or "late" in normalized:
        return DEFAULT_LATE, "description_late"
    if "früh" in normalized or "frueh" in normalized or "early" in normalized:
        return DEFAULT_EARLY, "description_early"
    if "nacht" in normalized or "night" in normalized:
        return DEFAULT_NIGHT, "description_night"

    # Check day_part column
    if day_part_lower in {"vm", "vormittag", "am", "morgen"}:
        return DEFAULT_EARLY, "daypart_vm"
    if day_part_lower in {"nm", "nachmittag", "pm", "abend"}:
        return DEFAULT_LATE, "daypart_nm"
    if "nacht" in day_part_lower:
        return DEFAULT_NIGHT, "daypart_night"

    # Default to early shift
    return DEFAULT_EARLY, "default"


def build_skill_overrides(skills: List[str], modality: str, prefer: str = "Notfall") -> Dict[str, int]:
    """Build skill_overrides in Skill×Modality format.

    Args:
        skills: List of skill names
        modality: Modality key (ct, mr, xray, mammo)
        prefer: Preferred skill to set to 1 (default: Notfall)

    Returns:
        Dict with Skill_modality keys
    """
    overrides = {}
    for skill in skills:
        key = f"{skill}_{modality}"
        overrides[key] = 1 if skill == prefer else 0
    return overrides


def guess_modality(activity: str, modalities: List[str]) -> Tuple[Optional[str], str]:
    """Guess modality based on keywords in the activity description."""
    normalized = activity.lower()
    keyword_map = {
        "ct": ["ct", "computed"],
        "mr": ["mr", "mrt", "magnet"],
        "xray": ["xray", "chir", "convention"],
        "mammo": ["mammo", "mammo", "gyn", "gyn"],
    }

    for modality in modalities:
        # reuse explicit modality key as a keyword
        if modality.lower() in normalized:
            return modality, "keyword"

    for modality, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in normalized:
                return modality if modality in modalities else None, "heuristic"

    return None, "unknown"




def build_rules(df: pd.DataFrame, skills: List[str], modalities: List[str], cols: dict) -> List[Dict]:
    """Build vendor mapping rules from CSV data.

    Args:
        df: DataFrame with activity data
        skills: List of skill names
        modalities: List of modality keys
        cols: Column name mappings

    Returns:
        List of rule dictionaries in NEW vendor_mappings format
    """
    activity_col = cols.get('activity', 'Beschreibung der Aktivität')
    day_part_col = cols.get('day_part', 'Tageszeit')

    counts = collections.Counter(
        df.get(activity_col, pd.Series(dtype=str)).dropna().astype(str)
    )

    if day_part_col in df.columns:
        day_part_lookup = (
            df[[activity_col, day_part_col]]
            .dropna(subset=[activity_col])
            .astype(str)
            .groupby(activity_col)
            .agg(lambda values: collections.Counter(values).most_common(1)[0][0])
        )
    else:
        day_part_lookup = {}

    rules: List[Dict] = []
    for activity, count in counts.most_common():
        day_part = day_part_lookup.get(activity, "") if (hasattr(day_part_lookup, 'empty') and not day_part_lookup.empty) or (isinstance(day_part_lookup, dict) and day_part_lookup) else ""
        modality, modality_source = guess_modality(activity, modalities)
        times, times_source = guess_times_from_activity(activity, day_part)

        note_parts = []
        if modality is None:
            modality = "TODO_modality"
            note_parts.append("modality unclear - please review")

        # Build skill_overrides in Skill×Modality format
        skill_overrides = build_skill_overrides(skills, modality if modality != "TODO_modality" else "ct")

        rule = {
            "match": activity,
            "type": "shift",
            "times": times,
            "skill_overrides": skill_overrides,
            "guessed_from": {
                "modality": modality_source,
                "times": times_source,
                "day_part": day_part,
                "occurrences": count,
            },
        }

        if note_parts:
            rule["notes"] = "; ".join(note_parts)

        rules.append(rule)

    return rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare medweb mapping YAML from CSV")
    parser.add_argument("--input", required=True, help="Path to medweb CSV file")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Path to write generated YAML (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Existing config.yaml to seed skills and shift names",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    config_path = Path(args.config)

    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    config = load_existing_config(config_path)
    skills = extract_skills(config)
    modalities = extract_modalities(config)

    try:
        df = pd.read_csv(input_path)
    except Exception as exc:  # pragma: no cover - CLI helper
        raise SystemExit(f"Failed to read CSV {input_path}: {exc}")

    vendor_mapping = config.get('vendor_mappings', {}).get('medweb', config.get('medweb_mapping', {}))
    cols = vendor_mapping.get('columns', {
        'date': 'Datum',
        'activity': 'Beschreibung der Aktivität',
        'employee_name': 'Name des Mitarbeiters',
        'employee_code': 'Code des Mitarbeiters',
        'day_part': 'Tageszeit'
    })
    activity_col = cols.get('activity', 'Beschreibung der Aktivität')

    if activity_col not in df.columns:
        raise SystemExit(
            f"CSV must contain column '{activity_col}'. Columns found: {list(df.columns)}"
        )

    rules = build_rules(df, skills, modalities, cols)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(input_path),
        "notes": (
            "Review time guesses and skill_overrides. TODO_* markers indicate fields "
            "that need manual confirmation before merging into config.yaml. "
            "This uses the NEW vendor_mappings format with embedded times."
        ),
        "vendor_mappings": {
            "medweb": {
                "columns": cols,
                "rules": rules
            }
        },
    }

    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)

    print(f"Generated {len(rules)} rules based on {input_path.name}")
    print(f"Skills used: {skills}")
    print(f"Modalities considered: {modalities}")
    print(f"Format: NEW vendor_mappings with embedded times and skill_overrides")
    print(f"Draft YAML written to {output_path}")


if __name__ == "__main__":
    main()
