# UC6 AdaptPlanToOccupancyChange — Acceptance Status

## Latest run

- **Command:** `PYTHONPATH="./backend:." behave tests/acceptance/features/UC6_AdaptPlanToOccupancyChange.feature`
- **Date:** 2026-06-07
- **Result:** **17 / 17 scenarios passed** (290 / 290 steps, 0 skipped, 0 undefined).

## Full regression (UC1–UC6)

- **Command:** `PYTHONPATH="./backend:." behave tests/acceptance/features/UC{1..6}_*.feature`
- **Result:** **6 features passed**, **101 / 101 scenarios** (1309 / 1309 steps).
- **Elapsed:** ~17.3 s.

## T4 failure-bundle cycles

**0** — single-pass T3 reached green. The one T3 micro-iteration touched cosmetic UI styling (removed `uppercase` Tailwind class so the decision pill text matched the expected lowercase string in S17). No failure bundle was packaged.

## Scenario index

| Scenario | Status |
|---|---|
| UC6-S01 Happy single-zone replan on +50% jump | pass |
| UC6-S02 Happy multi-zone replan when two of three cross the threshold | pass |
| UC6-S03 Mixed material and non-material yields material-only changed_zone_ids | pass |
| UC6-S04 No-replan when every zone change is below threshold | pass |
| UC6-S05 Threshold BELOW 29% is non-material | pass |
| UC6-S06 Threshold AT 30% is material | pass |
| UC6-S07 Zero-baseline edge — any new occupancy is material | pass |
| UC6-S08 Negative direction drop crosses threshold | pass |
| UC6-S09 No active plan exists | pass |
| UC6-S10 Unknown building id | pass |
| UC6-S11 Unknown zone id in payload | pass |
| UC6-S12 Empty occupancy_changes payload | pass |
| UC6-S13 Active plan resolves even when applied state is mixed dispatched/failed | pass |
| UC6-S14 Determinism — identical second payload sees zero delta | pass |
| UC6-S15 Cross-building isolation | pass |
| UC6-S16 Performance budget for 5-zone replanned path | pass |
| UC6-S17 UI flow via /adapt-plan | pass |
