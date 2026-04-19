# UC2 Acceptance Status

**Last run:** 2026-04-19
**Result:** ✅ 7 / 7 scenarios passed (65 steps, 0 failed)
**T4 cycles:** 0 — all scenarios passed on the first acceptance run; no failure bundle required.

## Scenario results

| Scenario | Result |
|---|---|
| UC2-S01 Successfully import a valid occupancy schedule | ✅ pass |
| UC2-S02 Unknown zone_id identifies the offending row | ✅ pass |
| UC2-S03 Invalid timestamp identifies the offending row | ✅ pass |
| UC2-S04 Non-integer occupancy_count identifies the offending row | ✅ pass |
| UC2-S05 Malformed header is reported with a header error | ✅ pass |
| UC2-S06 Empty file is rejected with a clear error | ✅ pass |
| UC2-S07 Import of 1000 rows completes within the time limit | ✅ pass |

## Regression notes

Full suite (UC1 + UC2) re-run after UC2 merge — 12 / 12 scenarios pass (2026-04-19).

## Commands

```bash
source .venv/bin/activate
cd frontend && npm run dev &
cd ..
PYTHONPATH="./backend:." behave tests/acceptance/features/UC2_ImportOccupancySchedule.feature
```
