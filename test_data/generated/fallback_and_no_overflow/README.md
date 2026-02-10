# fallback_and_no_overflow

Strict specialist-only and overflow fallback assignment checks.

## Files

- `master_medweb.csv`: parser input CSV
- `worker_skill_roster.json`: deterministic roster fixture
- `config.overlay.yaml`: medweb mapping + parser overlay config
- `expected_summary.json`: normalized expected parser + assignment summary

## Quick Validation

```bash
python scripts/gen_test_data.py --scenario fallback_and_no_overflow --run-tests
```
