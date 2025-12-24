#!/usr/bin/env python3
"""Export and import examination values (Skill×Modality weights) to/from CSV.

This standalone script allows admins to:
1. EXPORT: Generate a CSV showing the calculated weight for each Skill×Modality combination
2. IMPORT: Generate YAML template entries from a CSV to paste into config.yaml

Usage:
    # Export current config to CSV
    python exam_values.py export --config config.yaml --output exam_values.csv

    # Import from CSV to generate YAML template
    python exam_values.py import --input exam_values.csv --output exam_values_template.yaml

CSV Format:
    skill,ct,mr,xray,mammo
    Notfall,1.10,1.32,0.36,0.55
    MSK,0.80,0.96,0.26,0.40
    ...

Notes:
- Default weight = skill.weight × modality.factor
- skill_modality_overrides in config.yaml can override specific combinations
- The CSV uses skills as rows and modalities as columns for readability
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


DEFAULT_SKILLS = [
    "Notfall", "Privat", "Gyn", "Päd", "MSK",
    "Abdomen", "Chest", "Cardvask", "Uro"
]
DEFAULT_MODALITIES = ["ct", "mr", "xray", "mammo"]


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load config.yaml and return parsed dict."""
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise SystemExit(f"Failed to parse YAML: {e}")


def get_skills(config: Dict[str, Any]) -> List[str]:
    """Extract skill names from config, preserving order."""
    skills_config = config.get("skills", {})
    if skills_config:
        # Sort by display_order if available
        sorted_skills = sorted(
            skills_config.items(),
            key=lambda x: x[1].get("display_order", 999)
        )
        return [s[0] for s in sorted_skills]
    return DEFAULT_SKILLS


def get_modalities(config: Dict[str, Any]) -> List[str]:
    """Extract modality keys from config."""
    modalities_config = config.get("modalities", {})
    if modalities_config:
        return list(modalities_config.keys())
    return DEFAULT_MODALITIES


def calculate_exam_value(
    skill: str,
    modality: str,
    config: Dict[str, Any]
) -> float:
    """Calculate the exam value (weight) for a Skill×Modality combination.

    Default: skill.weight × modality.factor
    Can be overridden via skill_modality_overrides.
    """
    skills_config = config.get("skills", {})
    modalities_config = config.get("modalities", {})
    overrides = config.get("skill_modality_overrides", {})

    # Check for explicit override first
    if modality in overrides and skill in overrides[modality]:
        return float(overrides[modality][skill])

    # Calculate default: skill.weight × modality.factor
    skill_weight = skills_config.get(skill, {}).get("weight", 1.0)
    modality_factor = modalities_config.get(modality, {}).get("factor", 1.0)

    return skill_weight * modality_factor


def export_to_csv(config_path: Path, output_path: Path) -> None:
    """Export exam values from config to CSV.

    CSV format: skill as rows, modalities as columns
    """
    config = load_config(config_path)
    skills = get_skills(config)
    modalities = get_modalities(config)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Header row: skill + modality columns
        writer.writerow(["skill"] + modalities)

        # Data rows: one per skill
        for skill in skills:
            row = [skill]
            for modality in modalities:
                value = calculate_exam_value(skill, modality, config)
                # Use 3 decimal places for precision, strip trailing zeros
                formatted = f"{value:.3f}".rstrip('0').rstrip('.')
                row.append(formatted)
            writer.writerow(row)

    print(f"Exported {len(skills)} skills × {len(modalities)} modalities to {output_path}")
    print(f"Skills: {skills}")
    print(f"Modalities: {modalities}")


def import_from_csv(input_path: Path, output_path: Path, config_path: Path | None) -> None:
    """Import exam values from CSV and generate YAML template entries.

    Generates skill_modality_overrides for any values that differ from defaults.
    """
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    # Load existing config for default calculation (optional)
    config: Dict[str, Any] = {}
    if config_path and config_path.exists():
        config = load_config(config_path)

    # Read CSV
    with input_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise SystemExit("CSV file is empty")

    # Get modalities from CSV headers (all columns except 'skill')
    fieldnames = reader.fieldnames or []
    modalities = [col for col in fieldnames if col.lower() != "skill"]

    # Build overrides structure
    overrides: Dict[str, Dict[str, float]] = {}
    skill_weights: Dict[str, float] = {}
    modality_factors: Dict[str, float] = {}

    skills = []
    for row in rows:
        skill = row.get("skill", "").strip()
        if not skill:
            continue
        skills.append(skill)

        for modality in modalities:
            csv_value = row.get(modality, "").strip()
            if not csv_value:
                continue

            try:
                value = float(csv_value)
            except ValueError:
                print(f"Warning: Invalid value '{csv_value}' for {skill}_{modality}, skipping")
                continue

            # Calculate what the default would be
            default_value = calculate_exam_value(skill, modality, config)

            # Only add override if different from default
            # Use tolerance of 0.005 to account for CSV rounding (2 decimal places)
            if abs(value - default_value) > 0.005:
                if modality not in overrides:
                    overrides[modality] = {}
                overrides[modality][skill] = value

    # Also generate full skill and modality definitions for reference
    for row in rows:
        skill = row.get("skill", "").strip()
        if not skill:
            continue

        # Estimate skill weight from CT column (assumes CT factor = 1.0)
        if "ct" in row and row["ct"].strip():
            try:
                ct_value = float(row["ct"])
                ct_factor = config.get("modalities", {}).get("ct", {}).get("factor", 1.0)
                estimated_weight = ct_value / ct_factor
                skill_weights[skill] = estimated_weight
            except ValueError:
                pass

    # Generate output YAML
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(input_path),
        "notes": (
            "This file contains skill_modality_overrides for values that differ from "
            "the default calculation (skill.weight × modality.factor). "
            "Copy the skill_modality_overrides section to your config.yaml."
        ),
    }

    if overrides:
        result["skill_modality_overrides"] = overrides
        result["overrides_summary"] = (
            f"Found {sum(len(v) for v in overrides.values())} overrides "
            f"across {len(overrides)} modalities"
        )
    else:
        result["skill_modality_overrides"] = {}
        result["overrides_summary"] = (
            "No overrides needed - all values match default calculations"
        )

    # Include reference for skill weights if we estimated any
    if skill_weights:
        result["estimated_skill_weights"] = {
            "notes": "Estimated from CT column (assuming CT factor = 1.0)",
            "skills": skill_weights
        }

    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(result, f, sort_keys=False, allow_unicode=True)

    print(f"Processed {len(skills)} skills × {len(modalities)} modalities")
    if overrides:
        override_count = sum(len(v) for v in overrides.values())
        print(f"Generated {override_count} overrides in {output_path}")
    else:
        print(f"No overrides needed - all values match defaults")
    print(f"Template written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export/import examination values (Skill×Modality weights)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export current exam values to CSV
    python exam_values.py export --config config.yaml --output exam_values.csv

    # Import from edited CSV and generate config template
    python exam_values.py import --input exam_values.csv --output exam_overrides.yaml

    # Import with reference to existing config (for delta detection)
    python exam_values.py import --input exam_values.csv --config config.yaml --output exam_overrides.yaml
"""
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Export subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Export exam values from config.yaml to CSV"
    )
    export_parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml)"
    )
    export_parser.add_argument(
        "--output", "-o",
        default="exam_values.csv",
        help="Output CSV file path (default: exam_values.csv)"
    )

    # Import subcommand
    import_parser = subparsers.add_parser(
        "import",
        help="Import exam values from CSV and generate YAML template"
    )
    import_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input CSV file path"
    )
    import_parser.add_argument(
        "--output", "-o",
        default="exam_values_template.yaml",
        help="Output YAML template file (default: exam_values_template.yaml)"
    )
    import_parser.add_argument(
        "--config", "-c",
        default=None,
        help="Optional: existing config.yaml to compare against for delta detection"
    )

    args = parser.parse_args()

    if args.command == "export":
        export_to_csv(
            config_path=Path(args.config),
            output_path=Path(args.output)
        )
    elif args.command == "import":
        import_from_csv(
            input_path=Path(args.input),
            output_path=Path(args.output),
            config_path=Path(args.config) if args.config else None
        )


if __name__ == "__main__":
    main()
