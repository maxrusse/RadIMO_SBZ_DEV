# weighted_worker

Weighted and regular workers on the same skill/modality pool.

## Files

- `master_medweb.csv`: parser input CSV
- `worker_skill_roster.json`: deterministic roster fixture
- `config.overlay.yaml`: medweb mapping + parser overlay config
- `expected_summary.json`: normalized expected parser + assignment summary

## Quick Validation

```bash
python scripts/gen_test_data.py --scenario weighted_worker --run-tests
```
