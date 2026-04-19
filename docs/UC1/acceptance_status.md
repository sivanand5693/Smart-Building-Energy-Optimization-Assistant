# UC1 Acceptance Status

**Last run:** 2026-04-19
**Result:** ✅ 5 / 5 scenarios passed (47 steps, 0 failed)
**T4 cycles:** 1 (see `failure_bundles/UC1-S02_pydantic_422_vs_service_400.md`)

## Scenario results

| Scenario | Result |
|---|---|
| UC1-S01 Successfully register a valid building profile | ✅ pass |
| UC1-S02 Missing building name shows specific field error | ✅ pass |
| UC1-S03 Missing zone shows specific field error | ✅ pass |
| UC1-S04 Invalid schedule times show specific field error | ✅ pass |
| UC1-S05 Save completes within performance limit | ✅ pass |

## Regression notes

UC1 re-run after UC2 merge — 5 / 5 scenarios still pass (2026-04-19).

## Commands

```bash
source .venv/bin/activate
cd frontend && npm run dev &
cd ..
PYTHONPATH="./backend:." behave tests/acceptance/features/UC1_RegisterBuildingProfile.feature
```
