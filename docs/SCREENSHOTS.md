# Training Screenshots

This project includes a deterministic screenshot workflow for user training documentation.

## Goal

Produce reproducible screenshots that show realistic states:
- loaded schedules and staged prep data
- assignment outcomes after dummy clicks
- strict/no-fallback behavior
- filtered prep and worker-load views
- normal vs strict weight configuration

## One Command Flow

```bash
python scripts/capture_screenshots.py
```

This script will:
1. Run `scripts/apply_demo_data.py` to generate rich demo fixtures.
2. Start a local Flask server.
3. Load + preload schedule state.
4. Simulate deterministic API assignment clicks.
5. Capture a scene-based screenshot set.

To generate the step-by-step operator tutorial pack:

```bash
python scripts/capture_screenshots.py --scene-profile tutorial
```

## Output

Screenshots are saved to:

`../_docs/screenshots/radimo_cortex_playwright_training_<YYYY-MM-DD>/`

Tutorial profile output:

`../_docs/screenshots/radimo_cortex_playwright_tutorial_<YYYY-MM-DD>/`

Each run also writes:
- `manifest.json` (machine-readable scene metadata)
- `README.md` (human-readable scene list and route mapping)

## Useful Flags

```bash
python scripts/capture_screenshots.py --skip-prepare
python scripts/capture_screenshots.py --no-simulate-clicks
python scripts/capture_screenshots.py --scene-profile tutorial
python scripts/capture_screenshots.py --output-dir "C:\path\to\folder"
python scripts/capture_screenshots.py --width 1920 --height 1080
```

## Notes

- If Playwright browser binaries are missing, install with:
  - `python -m playwright install chromium`
- This workflow is intended for documentation snapshots, not performance benchmarking.
