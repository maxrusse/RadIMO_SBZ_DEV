"""
Prepare deterministic demo data for local UI/screenshot workflows.

This script:
1) Writes uploads/master_medweb.csv with rows for target + preload date.
2) Copies demo button weights to data/button_weights.json.
3) Optionally triggers load-today + preload-next-day via Flask test client.
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

DEMO_WEIGHTS_PATH = ROOT / "test_data" / "demo" / "button_weights_demo.json"


def _resolve_demo_weights() -> Path:
    if DEMO_WEIGHTS_PATH.exists():
        return DEMO_WEIGHTS_PATH
    raise FileNotFoundError(
        "Missing demo button weights. Expected: "
        f"{DEMO_WEIGHTS_PATH}"
    )


def _write_demo_master_csv(target: date, preload: date) -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    # Activities intentionally map to rules already present in config.yaml.
    for d in (target, preload):
        ds = d.strftime("%d.%m.%Y")
        rows.extend(
            [
                [ds, "Assistent Notfall", "Dr. Demo Notfall", "DM01", "VM"],
                [ds, "OA MR", "Dr. Demo Privat MR", "DM02", "VM"],
                [ds, "OA / FA Chir", "Dr. Demo Privat XRAY", "DM03", "VM"],
                [ds, "OA / FA Gyn", "Dr. Demo Privat Mammo", "DM04", "VM"],
            ]
        )

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

    _write_demo_master_csv(target=target, preload=preload)
    weights_src = _copy_demo_weights()

    result: dict[str, Any] = {
        "master_csv_path": str(MASTER_CSV_PATH.relative_to(ROOT)),
        "button_weights_path": str(BUTTON_WEIGHTS_PATH.relative_to(ROOT)),
        "button_weights_source": str(weights_src.relative_to(ROOT)),
        "target_date": target.isoformat(),
        "preload_date": preload.isoformat(),
    }

    if not args.no_load:
        result["load_result"] = _load_demo_state(preload=preload)

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
