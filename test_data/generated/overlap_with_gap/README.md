# overlap_with_gap

Overlapping shifts with a standalone gap intent for one worker.

## Files

- `master_medweb.csv`: parser input CSV
- `worker_skill_roster.json`: deterministic roster fixture
- `config.overlay.yaml`: medweb mapping + parser overlay config
- `expected_summary.json`: normalized expected parser + assignment summary

## Quick Validation

```bash
python scripts/gen_test_data.py --scenario overlap_with_gap --run-tests
```
