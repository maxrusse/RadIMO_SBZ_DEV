"""
Prepare deterministic demo data for local UI/screenshot workflows.

This script:
1) Writes uploads/master_medweb.csv with rich rows for target + preload date.
2) Writes a deterministic demo worker roster into data/worker_skill_roster.json.
3) Copies demo button weights to data/button_weights.json.
4) Optionally triggers load-today + preload-next-day via Flask test client.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
UPLOADS_DIR = ROOT / "uploads"
DATA_DIR = ROOT / "data"
MASTER_CSV_PATH = UPLOADS_DIR / "master_medweb.csv"
BUTTON_WEIGHTS_PATH = DATA_DIR / "button_weights.json"
WORKER_ROSTER_PATH = DATA_DIR / "worker_skill_roster.json"

DEMO_WEIGHTS_PATH = ROOT / "test_data" / "demo" / "button_weights_demo.json"
SKILLS = ["notfall", "privat", "gyn", "paed", "msk-haut", "abd-onco", "card-thor", "uro", "kopf-hals"]
MODALITIES = ["ct", "mr", "xray", "mammo"]


DEMO_ACTIVITY_PLAN: list[tuple[str, list[str]]] = [
    ("Assistent Notfall", ["KM15", "HB16", "LV08"]),
    ("UNZ Assistent", ["MS11"]),
    ("OA CT", ["AK18"]),
    ("OA MR", ["CP20", "TN31"]),
    ("SBZ: SBZ Privatpatienten", ["TY33"]),
    ("OA / FA Chir", ["ER14", "FH19"]),
    ("OA / FA Gyn", ["JR06", "LC02"]),
    ("Assistent Gyn", ["MG17"]),
    ("Assistent Päd", ["NP25"]),
    ("Assistent AbdOnco", ["OB22"]),
    ("Assistent CardThor", ["PK12"]),
    ("Assistent Uro", ["QL10"]),
    ("Assistent KopfHals", ["RM13"]),
    ("FA/Fellow MskHaut", ["ST27"]),
    ("SBZ Spät Assistent", ["UV09"]),
    ("3. Dienst", ["WX07"]),
]

# Weekday-aware gap activities guarantee visible split/blocked schedule rows.
GAP_BY_WEEKDAY = {
    0: "Mult. Myelom Board (Mo 15:30)",
    1: "Emphysem-Board, Di 16:00 Uhr",
    2: "ILD-Board (Mi 15:00, 14-tägig)",
    3: "Uro-Board (Do 14:30)",
    4: "IPOK (Fr 13 Uhr, Konf.raum 5)",
    5: "SBZ Geräteassistenz",
    6: "SBZ Geräteassistenz",
}

# Worker IDs are stable and map to realistic mixed skill distributions.
DEMO_WORKERS: list[dict[str, Any]] = [
    {
        "id": "KM15",
        "name": "Dr. Kora Meier (KM15)",
        "global_modifier": 1.0,
        "overrides": {"notfall_ct": 1, "notfall_mr": 1, "notfall_xray": 1, "notfall_mammo": 1, "privat_ct": -1},
    },
    {
        "id": "HB16",
        "name": "Dr. Hannes Berg (HB16)",
        "global_modifier": 0.95,
        "overrides": {"notfall_ct": 1, "notfall_mr": 1, "notfall_xray": 1, "notfall_mammo": 1},
    },
    {
        "id": "LV08",
        "name": "Dr. Lara Vogt (LV08)",
        "global_modifier": 1.05,
        "overrides": {"notfall_ct": 1, "notfall_mr": 1, "notfall_xray": 1, "notfall_mammo": 1},
    },
    {
        "id": "MS11",
        "name": "Dr. Milo Stein (MS11)",
        "global_modifier": 1.0,
        "overrides": {"notfall_ct": 1, "notfall_mr": 1, "notfall_xray": 1, "notfall_mammo": 1},
    },
    {"id": "AK18", "name": "Dr. Andrea Krause (AK18)", "global_modifier": 0.9, "overrides": {"privat_ct": 1}},
    {"id": "CP20", "name": "Dr. Claudia Peters (CP20)", "global_modifier": 1.25, "overrides": {"privat_mr": 1}},
    {"id": "TN31", "name": "Dr. Theo Noll (TN31)", "global_modifier": 1.1, "overrides": {"privat_mr": 1}},
    {"id": "TY33", "name": "Dr. Tilda Young (TY33)", "global_modifier": 1.0, "overrides": {"privat_ct": 1, "privat_mr": 1}},
    {"id": "ER14", "name": "Dr. Eva Richter (ER14)", "global_modifier": 1.0, "overrides": {"privat_xray": 1}},
    {"id": "FH19", "name": "Dr. Felix Hartmann (FH19)", "global_modifier": 1.0, "overrides": {"privat_xray": 1, "msk-haut_xray": 1}},
    {"id": "JR06", "name": "Dr. Julia Reimer (JR06)", "global_modifier": 1.0, "overrides": {"privat_mammo": 1, "gyn_mammo": 1}},
    {"id": "LC02", "name": "Dr. Lina Cramer (LC02)", "global_modifier": 0.95, "overrides": {"privat_mammo": 1, "gyn_mammo": 1}},
    {
        "id": "MG17",
        "name": "Dr. Mara Grimm (MG17)",
        "global_modifier": 1.0,
        "modifier": 0.7,
        "overrides": {"gyn_ct": 1, "gyn_mr": 1, "gyn_mammo": "w", "notfall_ct": -1},
    },
    {"id": "NP25", "name": "Dr. Noah Pohl (NP25)", "global_modifier": 1.0, "overrides": {"paed_ct": 1, "paed_mr": 1, "paed_xray": 1}},
    {
        "id": "OB22",
        "name": "Dr. Olivia Brandt (OB22)",
        "global_modifier": 1.0,
        "modifier": 0.6,
        "overrides": {"abd-onco_ct": 1, "abd-onco_mr": "w"},
    },
    {"id": "PK12", "name": "Dr. Paul Koch (PK12)", "global_modifier": 1.0, "overrides": {"card-thor_ct": 1, "card-thor_mr": 1}},
    {"id": "QL10", "name": "Dr. Quentin Lang (QL10)", "global_modifier": 1.0, "overrides": {"uro_ct": 1, "uro_mr": 1}},
    {"id": "RM13", "name": "Dr. Rina Maurer (RM13)", "global_modifier": 1.0, "overrides": {"kopf-hals_ct": 1, "kopf-hals_mr": 1}},
    {"id": "ST27", "name": "Dr. Sven Thaler (ST27)", "global_modifier": 1.0, "overrides": {"msk-haut_ct": 1, "msk-haut_mr": 1, "msk-haut_xray": 1}},
    {"id": "UV09", "name": "Dr. Ute Vogler (UV09)", "global_modifier": 1.15, "overrides": {"notfall_mr": 0, "notfall_xray": 0}},
    {"id": "WX07", "name": "Dr. Willem Xander (WX07)", "global_modifier": 1.05, "overrides": {"notfall_xray": 1}},
    {
        "id": "GP40",
        "name": "Dr. Greta Pause (GP40)",
        "global_modifier": 1.0,
        "overrides": {"notfall_ct": -1, "notfall_mr": -1, "notfall_xray": -1, "notfall_mammo": -1},
    },
]


def _resolve_demo_weights() -> Path:
    if DEMO_WEIGHTS_PATH.exists():
        return DEMO_WEIGHTS_PATH
    raise FileNotFoundError(
        "Missing demo button weights. Expected: "
        f"{DEMO_WEIGHTS_PATH}"
    )


def _skill_modality_keys() -> list[str]:
    return [f"{skill}_{modality}" for skill in SKILLS for modality in MODALITIES]


def _build_worker_entry(*, full_name: str, global_modifier: float, modifier: float | None, overrides: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {key: 0 for key in _skill_modality_keys()}
    entry["full_name"] = full_name
    entry["global_modifier"] = float(global_modifier)
    if modifier is not None:
        entry["modifier"] = float(modifier)
    for key, value in overrides.items():
        if key in entry:
            entry[key] = value
    return entry


def _build_worker_catalog() -> dict[str, dict[str, Any]]:
    return {w["id"]: w for w in DEMO_WORKERS}


def _gap_activity_for_day(day: date) -> str:
    return GAP_BY_WEEKDAY.get(day.weekday(), "SBZ Geräteassistenz")


def _write_demo_master_csv(target: date, preload: date) -> dict[str, int]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    worker_catalog = _build_worker_catalog()
    rows: list[list[str]] = []

    # Activities intentionally map to rules already present in config.yaml.
    for current_day in (target, preload):
        ds = current_day.strftime("%d.%m.%Y")
        for activity, worker_ids in DEMO_ACTIVITY_PLAN:
            for worker_id in worker_ids:
                worker = worker_catalog[worker_id]
                rows.append([ds, activity, worker["name"], worker_id, "VM"])

        # Add one split-shift gap worker and one standalone gap worker.
        day_gap = _gap_activity_for_day(current_day)
        rows.append([ds, day_gap, worker_catalog["PK12"]["name"], "PK12", "VM"])
        rows.append([ds, day_gap, worker_catalog["GP40"]["name"], "GP40", "VM"])

    with MASTER_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Datum",
                "Beschreibung der Aktivität",
                "Name des Mitarbeiters",
                "Code des Mitarbeiters",
                "Tageszeit",
            ]
        )
        writer.writerows(rows)

    return {"row_count": len(rows), "worker_count": len(worker_catalog)}


def _write_demo_roster() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    roster: dict[str, dict[str, Any]] = {}
    for worker in DEMO_WORKERS:
        roster[worker["id"]] = _build_worker_entry(
            full_name=worker["name"],
            global_modifier=worker.get("global_modifier", 1.0),
            modifier=worker.get("modifier"),
            overrides=worker.get("overrides", {}),
        )
    WORKER_ROSTER_PATH.write_text(
        json.dumps(roster, ensure_ascii=True, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return len(roster)


def _copy_demo_weights() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    src = _resolve_demo_weights()
    shutil.copy2(src, BUTTON_WEIGHTS_PATH)
    return src


def _load_demo_state(preload: date) -> dict[str, Any]:
    from app import app

    with app.test_client() as client:
        load_today_resp = client.post("/load-today-from-master")
        preload_resp = client.post(
            "/preload-from-master",
            json={"target_date": preload.isoformat()},
        )
        return {
            "load_today": {
                "status_code": load_today_resp.status_code,
                "body": load_today_resp.get_json(silent=True),
            },
            "preload": {
                "status_code": preload_resp.status_code,
                "body": preload_resp.get_json(silent=True),
            },
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare deterministic demo data.")
    parser.add_argument(
        "--target-date",
        type=str,
        default=date.today().isoformat(),
        help="Target date (YYYY-MM-DD) for today's live load.",
    )
    parser.add_argument(
        "--preload-date",
        type=str,
        default=None,
        help="Preload date (YYYY-MM-DD) for staged next day. Default: target + 1 day.",
    )
    parser.add_argument(
        "--no-load",
        action="store_true",
        help="Do not call /load-today-from-master and /preload-from-master.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = date.fromisoformat(args.target_date)
    preload = (
        date.fromisoformat(args.preload_date)
        if args.preload_date
        else target + timedelta(days=1)
    )
    if preload <= target:
        raise ValueError("preload-date must be after target-date")

    csv_stats = _write_demo_master_csv(target=target, preload=preload)
    roster_count = _write_demo_roster()
    weights_src = _copy_demo_weights()

    result: dict[str, Any] = {
        "master_csv_path": str(MASTER_CSV_PATH.relative_to(ROOT)),
        "master_csv_rows": csv_stats["row_count"],
        "button_weights_path": str(BUTTON_WEIGHTS_PATH.relative_to(ROOT)),
        "button_weights_source": str(weights_src.relative_to(ROOT)),
        "worker_roster_path": str(WORKER_ROSTER_PATH.relative_to(ROOT)),
        "worker_roster_size": roster_count,
        "target_date": target.isoformat(),
        "preload_date": preload.isoformat(),
    }

    if not args.no_load:
        result["load_result"] = _load_demo_state(preload=preload)

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
