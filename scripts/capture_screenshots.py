"""
Capture full-page screenshots for main RadIMO pages using Playwright.

Default flow:
1) Prepare deterministic demo data via scripts/apply_demo_data.py.
2) Start local Flask server on 127.0.0.1:5050.
3) Capture screenshots for key pages into _docs/screenshots/<timestamped_dir>.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ("01_dashboard", "/"),
    ("02_by_skill", "/by-skill"),
    ("03_timetable", "/timetable"),
    ("04_upload", "/upload"),
    ("05_skill_roster", "/skill-roster"),
    ("06_prep_today", "/prep-today"),
    ("07_prep_tomorrow", "/prep-tomorrow"),
    ("08_worker_load", "/worker-load"),
    ("09_button_weights", "/button-weights"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture RadIMO screenshots.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for local Flask app.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5050,
        help="Port for local Flask app.",
    )
    parser.add_argument(
        "--target-date",
        default=date.today().isoformat(),
        help="Target date for demo prep (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--preload-date",
        default=None,
        help="Preload date for demo prep (YYYY-MM-DD). Default: target + 1 day.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(
            ROOT.parent / "_docs" / "screenshots" / f"radimo_cortex_playwright_{date.today().isoformat()}"
        ),
        help="Output folder for PNG files.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1920,
        help="Viewport width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1080,
        help="Viewport height.",
    )
    parser.add_argument(
        "--startup-timeout-sec",
        type=float,
        default=20.0,
        help="Server readiness timeout.",
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Skip running scripts/apply_demo_data.py.",
    )
    return parser.parse_args()


def _wait_for_health(base_url: str, timeout_sec: float) -> None:
    deadline = time.time() + timeout_sec
    health_url = f"{base_url}/healthz"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:  # noqa: S310
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Server did not become ready: {health_url}")


def _prepare_demo(py_exe: str, target_date: str, preload_date: str | None) -> None:
    cmd = [py_exe, str(ROOT / "scripts" / "apply_demo_data.py"), "--target-date", target_date]
    if preload_date:
        cmd.extend(["--preload-date", preload_date])
    subprocess.run(cmd, cwd=ROOT, check=True)


def _capture_pages(base_url: str, out_dir: Path, width: int, height: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()

        for name, path in PAGES:
            page.goto(f"{base_url}{path}", wait_until="networkidle", timeout=60_000)
            target = out_dir / f"{name}.png"
            page.screenshot(path=str(target), full_page=True)
            print(f"{target} ({target.stat().st_size} bytes)")

        context.close()
        browser.close()


def main() -> int:
    args = parse_args()
    py_exe = sys.executable
    base_url = f"http://{args.host}:{args.port}"
    out_dir = Path(args.output_dir)

    if not args.skip_prepare:
        _prepare_demo(
            py_exe=py_exe,
            target_date=args.target_date,
            preload_date=args.preload_date,
        )

    server_cmd = [py_exe, "-m", "flask", "--app", "app", "run", "--host", args.host, "--port", str(args.port)]
    server_proc = subprocess.Popen(server_cmd, cwd=ROOT)
    try:
        _wait_for_health(base_url=base_url, timeout_sec=args.startup_timeout_sec)
        _capture_pages(
            base_url=base_url,
            out_dir=out_dir,
            width=args.width,
            height=args.height,
        )
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
