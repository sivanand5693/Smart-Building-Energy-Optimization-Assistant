# UC3 Acceptance Status

**Last run:** 2026-06-01
**Result:** 17 / 17 scenarios passed (180 steps, 0 failed)
**T4 cycles:** 0 — all scenarios passed on the first acceptance run after expansion; no failure bundle required.

## Scenario results

| Scenario | Result |
|---|---|
| UC3-S01 Successful forecast for all zones of a building | pass |
| UC3-S02 Missing occupancy data fails atomically | pass |
| UC3-S03 Missing weather data fails atomically | pass |
| UC3-S04 Missing device-state data fails atomically | pass |
| UC3-S05 Forecast records include structured timestamp and zone_id fields | pass |
| UC3-S06 Forecast run completes within performance budget | pass |
| UC3-S07 Failed run preserves prior forecasts | pass |
| UC3-S08 Single-zone happy path | pass |
| UC3-S09 Larger multi-zone happy path | pass |
| UC3-S10 Determinism across re-runs | pass |
| UC3-S11 Cross-building isolation | pass |
| UC3-S12 Building with zero zones | pass |
| UC3-S13 Unknown building id | pass |
| UC3-S14 Multiple zones missing occupancy | pass |
| UC3-S15 Multiple missing input categories | pass |
| UC3-S16 UI error gating after failed run | pass |
| UC3-S17 Forecast model_version is stamped on every row | pass |

## Expansion notes (2026-06-01)

- S01–S07 unchanged from initial run; S08–S17 appended for ≥15-scenario coverage target.
- Step-definitions file refactored to track buildings by name (`context.buildings_by_name`) so multi-building scenarios (S11) and named lookups remain correct after seeding a second building.
- New step defs added: `a building "X" exists with no zones` (S12), `triggers a forecast run for an unknown building id` (S13), `predicted_kwh per zone is captured as the baseline` / `matches the baseline exactly` (S10), `user triggers a forecast run … via the ForecastsPage` (S16), `ForecastsPage shows an error banner listing` (S16), `ForecastsPage displays no forecast rows` (S16), `every persisted demand_forecast row has a non-empty model_version` (S17), distinct-zone-id and distinct-predicted-kwh oracles (S09).
- No implementation changes required — the existing service already raises `ForecastInputsMissing(["building"|"zones"|"occupancy"|"weather"|"device_state"])` precisely as the new scenarios assert.

## Regression notes

UC1 + UC2 + UC3 combined regression: 50 / 50 scenarios pass, 498 steps, 0 failures (2026-06-01).

## Commands

```bash
source .venv/bin/activate
cd frontend && npm run dev &
cd ..
PYTHONPATH="./backend:." behave tests/acceptance/features/UC3_ForecastZoneDemand.feature
```
