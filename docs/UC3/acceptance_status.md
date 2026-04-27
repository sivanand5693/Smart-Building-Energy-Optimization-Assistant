# UC3 Acceptance Status

**Last run:** 2026-04-27
**Result:** ✅ 7 / 7 scenarios passed (69 steps, 0 failed)
**T4 cycles:** 0 — all scenarios passed on the first acceptance run; no failure bundle required.

## Scenario results

| Scenario | Result |
|---|---|
| UC3-S01 Successful forecast for all zones of a building | ✅ pass |
| UC3-S02 Missing occupancy data fails atomically | ✅ pass |
| UC3-S03 Missing weather data fails atomically | ✅ pass |
| UC3-S04 Missing device-state data fails atomically | ✅ pass |
| UC3-S05 Forecast records include structured timestamp and zone_id fields | ✅ pass |
| UC3-S06 Forecast run completes within performance budget | ✅ pass |
| UC3-S07 Failed run preserves prior forecasts | ✅ pass |

## Regression notes

Full UC1 + UC2 + UC3 regression — 19 / 19 scenarios pass, 181 steps, 0 failures (2026-04-27).

## Commands

```bash
source .venv/bin/activate
cd frontend && npm run dev &
cd ..
PYTHONPATH="./backend:." behave tests/acceptance/features/UC3_ForecastZoneDemand.feature
```
