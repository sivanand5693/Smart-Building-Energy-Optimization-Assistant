# UC2 Acceptance Status

**Last run:** 2026-05-11 (suite expanded from 7 to 16 scenarios)
**Result:** 16 / 16 scenarios passed (145 steps, 0 failed)
**T4 cycles:** 0 — all 9 new scenarios (S08–S16) passed on the first acceptance run; no failure bundle required.

## Scenario results

| Scenario | Result |
|---|---|
| UC2-S01 Successfully import a valid occupancy schedule | pass |
| UC2-S02 Unknown zone_id identifies the offending row | pass |
| UC2-S03 Invalid timestamp identifies the offending row | pass |
| UC2-S04 Non-integer occupancy_count identifies the offending row | pass |
| UC2-S05 Malformed header is reported with a header error | pass |
| UC2-S06 Empty file is rejected with a clear error | pass |
| UC2-S07 Import of 1000 rows completes within the time limit | pass |
| UC2-S08 Zone belonging to another building is rejected | pass |
| UC2-S09 Negative occupancy_count identifies the offending row | pass |
| UC2-S10 Non-integer zone_id identifies the offending row | pass |
| UC2-S11 Wrong column count is reported as a row error | pass |
| UC2-S12 Multiple invalid rows are all reported atomically | pass |
| UC2-S13 Blank lines between data rows are skipped, valid rows imported | pass |
| UC2-S14 Header with surrounding whitespace is tolerated | pass |
| UC2-S15 Submit is disabled until both building and file are selected | pass |
| UC2-S16 File containing only a header row is rejected | pass |

## Regression notes

- Full suite (UC1 + UC2 + UC3) re-run after the UC2 expansion: **40 / 40 scenarios pass**, 387 steps, 7.3s (2026-05-11).
- Prior baseline (pre-expansion): 31 / 31 pass (after UC1 expansion, 2026-05-11).

## Commands

```bash
source .venv/bin/activate
cd frontend && npm run dev &
cd ..
PYTHONPATH="./backend:." behave tests/acceptance/features/UC2_ImportOccupancySchedule.feature
```

## Notes

- S14 (header whitespace tolerance) documents the **current behavior** of `BuildingService.import_occupancy_schedule`: header cells are stripped via `[h.strip() for h in header]` before comparison with `EXPECTED_HEADER`. No code change was required to make this scenario pass.
- S16 (header-only file) is rejected with the file-level error `"no data rows found"` raised when zero records are parsed; surfaced through the `header-error` panel because it has `row == null`.
- A second-building seeder (`a second building "X" exists with zone "Y"`) was added to support S08 cross-building isolation tests.
