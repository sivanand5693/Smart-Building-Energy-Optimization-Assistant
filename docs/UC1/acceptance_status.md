# UC1 Acceptance Status

**Last run:** 2026-05-11
**Result:** 17 / 17 scenarios passed (173 steps, 0 failed)
**T4 cycles:** 3
- `failure_bundles/UC1-S02_pydantic_422_vs_service_400.md` (original UC1 T3 run)
- `failure_bundles/UC1-S10_duplicate_zone_names.md` (expansion run — duplicate zone-name validation)
- `failure_bundles/UC1-S14_unique_building_name_constraint.md` (expansion run — drop `buildings.name` unique constraint)

## Scenario results

| Scenario | Result |
|---|---|
| UC1-S01 Successfully register a valid building profile | pass |
| UC1-S02 Missing building name shows specific field error | pass |
| UC1-S03 Missing zone shows specific field error | pass |
| UC1-S04 Invalid schedule times show specific field error | pass |
| UC1-S05 Save completes within performance limit | pass |
| UC1-S06 Multiple zones with multiple devices each are persisted | pass |
| UC1-S07 Multiple operating schedules are persisted | pass |
| UC1-S08 Missing device type shows specific field error | pass |
| UC1-S09 Zone with no devices shows specific field error | pass |
| UC1-S10 Duplicate zone names within the same building show field error | pass |
| UC1-S11 Schedule end_time before start_time is rejected | pass |
| UC1-S12 Building name with special characters is accepted | pass |
| UC1-S13 Form re-population after validation failure preserves entered values | pass |
| UC1-S14 Two buildings with the same name are both persisted with distinct IDs | pass |
| UC1-S15 Whitespace-only building name is rejected as missing | pass |
| UC1-S16 Schedule with equal start and end time is rejected | pass |
| UC1-S17 Confirmation displays the persisted building ID and it matches the stored record | pass |

## Regression notes

- 2026-04-19: initial 5/5 pass after T4 cycle 1.
- 2026-04-19: re-run after UC2 merge — 5/5 still pass.
- 2026-05-11: UC1 scenario suite expanded from 5 to 17. Two new T4 cycles required:
  - S10: added duplicate-zone-name check to `BuildingService._validate` (error key `zones`).
  - S14: dropped `unique=True` on `BuildingModel.name`; new Alembic migration `b4e9c1a07f23_uc1_drop_building_name_unique` applied to dev and test DBs.
- 2026-05-11: full regression across UC1+UC2+UC3 — 31 / 31 scenarios pass.

## Commands

```bash
source .venv/bin/activate
cd frontend && npm run dev &
cd ..
PYTHONPATH="./backend:." behave tests/acceptance/features/UC1_RegisterBuildingProfile.feature
```
