# Generated Test Data

RadIMO includes a deterministic scenario pipeline to support both:
- automated integration tests in CI
- manual end-to-end checks in the admin portal

Generated artifacts live under `test_data/generated/`.

Demo fixtures live under `test_data/demo/`.

---

## What Gets Generated

For each scenario folder (`test_data/generated/<scenario>/`):
- `master_medweb.csv`: parser input CSV
- `worker_skill_roster.json`: deterministic roster fixture for that scenario
- `config.overlay.yaml`: minimal parser config overlay (`medweb_mapping`, balancer defaults)
- `expected_summary.json`: normalized expected output used by tests
- `README.md`: quick scenario-local instructions

Global index:
- `test_data/generated/index.json`

---

## Scenarios (v1)

1. `baseline_multimodality`
2. `overlap_with_gap`
3. `weighted_worker`
4. `fallback_and_no_overflow`

---

## Generate Fixtures

From repository root:

```bash
python scripts/gen_test_data.py --scenario all
```

Generate one scenario:

```bash
python scripts/gen_test_data.py --scenario overlap_with_gap
```

Use a custom target date:

```bash
python scripts/gen_test_data.py --scenario all --target-date 2026-02-10
```

---

## Validate Generated Scenarios

Run generated scenario tests:

```bash
python -m unittest tests.test_generated_scenarios -v
```

Generate and validate in one step:

```bash
python scripts/gen_test_data.py --scenario all --run-tests
```

---

## Full Test Suite

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## Demo Data (Screenshots / Manual UI)

Use `scripts/apply_demo_data.py` to create a deterministic live/staged dataset
that matches the default `config.yaml` mapping rules.

```bash
python scripts/apply_demo_data.py
```

This writes:
- `uploads/master_medweb.csv`
- `data/button_weights.json` (from `test_data/demo/button_weights_demo.json`)

Then it triggers:
- `POST /load-today-from-master`
- `POST /preload-from-master` (next day)

---

## Screenshot Automation (Playwright)

```bash
python scripts/capture_screenshots.py
```

Default output folder:
- `_docs/screenshots/radimo_cortex_playwright_<today>/`

---

## Manual Portal Check

1. Start app locally (`flask --app app run --debug`).
2. Open admin page `/upload`.
3. Upload `test_data/generated/<scenario>/master_medweb.csv`.
4. Use **Reset Today** and inspect `/`, `/timetable`, `/prep-today`.
5. If needed, temporarily replace `data/worker_skill_roster.json` with scenario roster fixture.

---

## Notes

- Generated fixtures are deterministic for the same scenario + date.
- The gap behavior in current tests is intentional: removing a gap does not auto-merge/fill shift segments.
- `test_data/demo/` is the canonical demo fixture location.
