# baseline_multimodality

Baseline multi-modality shifts without overlaps or gaps.

## Files

- `master_medweb.csv`: parser input CSV
- `worker_skill_roster.json`: deterministic roster fixture
- `config.overlay.yaml`: medweb mapping + parser overlay config
- `expected_summary.json`: normalized expected parser + assignment summary

## Quick Validation

```bash
python scripts/gen_test_data.py --scenario baseline_multimodality --run-tests
```
