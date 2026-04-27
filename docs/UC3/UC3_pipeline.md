# UC3 ForecastZoneDemand — Full Pipeline Record

## Metadata
- **Use Case ID:** UC3
- **Name:** ForecastZoneDemand
- **Started:** 2026-04-27
- **Last updated:** 2026-04-27 (T1 stage complete)
- **Status:** in-progress
- **Driver:** uc-pipeline-agent (executed inline by main session)

## Use Case Statement (verbatim from `ref/Project4_UseCases.docx`)

> **Use Case 3: ForecastZoneDemand**
>
> **Participating actors:** Initiated by Scheduler. Communicates with Forecasting Service.
>
> **Flow of events:**
> 1. The Scheduler triggers the "Forecast Zone Demand" function on a configured time interval.
> 2. The system gathers current occupancy, weather, and device-state data for all zones.
> 3. The system runs the demand forecasting model and calculates energy demand per zone.
> 4. The system stores the demand estimates with timestamps and zone IDs.
> 5. The system makes the forecast values available to the Optimization Service.
>
> **Entry condition:** A building profile, an occupancy schedule, and current weather and device data are available.
>
> **Exit conditions:** Zone-level demand forecasts with timestamps and zone IDs are stored, OR missing input data is reported and no forecast is produced.
>
> **Quality requirements:** Forecasts include timestamps and zone IDs as structured fields. Processing completes within 6 seconds.

---

## T1 — Structured Requirement and Gherkin

### Part A) Structured Requirement

See `docs/UC3/structured_requirement.md` for the full content. Summary:

- **Goal:** Persist a per-zone demand forecast (kWh) for every zone of a target building, atomically, on Scheduler trigger.
- **Triggering boundary for tests:** `POST /api/buildings/{id}/forecasts/run` (production scheduling deferred — A4).
- **External dependencies (all mocked via test doubles in acceptance):** `ForecastModelAdapter`, `WeatherAdapter`, `DeviceStateAdapter`.
- **Persistence:** new `demand_forecast` table — fields `id`, `zone_id`, `timestamp`, `predicted_kwh`, `model_version`, `created_at`.
- **Quality budget:** < 6000 ms wall-clock per run for ≤ 10 zones.
- **Atomicity rule:** any missing input fails the entire run; previously stored forecasts remain intact.
- **Assumptions:** A1–A7 (model adapter, weather adapter, device-state adapter, HTTP-trigger boundary, viewer UI, missing-input definition, model_version field). Production scheduler integration is deferred (A4).

### Part B) Acceptance Checks Table

See `docs/UC3/structured_requirement.md` §B.

### Part C) Acceptance Oracles

See `docs/UC3/structured_requirement.md` §C. Six oracles: UI, persistence, atomicity, field-structure, performance, error.

### Part D) Gherkin Feature File

See `tests/acceptance/features/UC3_ForecastZoneDemand.feature`. Seven scenarios:

| ID | Title | Type |
|---|---|---|
| UC3-S01 | Successful forecast for all zones of a building | Happy path |
| UC3-S02 | Missing occupancy data fails atomically | Negative |
| UC3-S03 | Missing weather data fails atomically | Negative |
| UC3-S04 | Missing device-state data fails atomically | Negative |
| UC3-S05 | Forecast records include structured timestamp and zone_id | Persistence + structure |
| UC3-S06 | Forecast run completes within performance budget | NFR |
| UC3-S07 | Failed run preserves prior forecasts | Atomicity |

---

## T2 — UI, DB, and Harness Design

### Part A) UI Design Summary
See `docs/UC3/ui_design.md`. Single page `ForecastsPage` at `/forecasts`. Inputs: building selector + "Run forecast" button. Outputs: success panel + per-zone forecast table (with stable `forecast-row-{zone_id}` testids) + error panel with `missingInputs` list. Failed runs leave any prior table contents intact (atomicity oracle).

### Part B) Database Design Summary
See `docs/UC3/db_design.md`. New table `demand_forecasts` (`id`, `zone_id` FK, `timestamp`, `predicted_kwh`, `model_version`, `created_at`) with index on `(zone_id, timestamp DESC)`. No changes to UC1/UC2 tables. Acceptance reset truncates `demand_forecasts` first.

### Part C) Service / Control Design Summary
See `docs/UC3/harness_design.md` Part C. New `ForecastService.run_forecast(building_id)` validates four inputs (zones, occupancy, weather, device_state), then runs the forecast model per zone and persists atomically. Three new adapter interfaces: `ForecastModelAdapter`, `WeatherAdapter`, `DeviceStateAdapter`. New repository: `DemandForecastRepository`. New routes: `POST .../forecasts/run`, `GET .../forecasts/latest`.

### Part D) Acceptance Harness Design
See `docs/UC3/harness_design.md` Part D. Three deterministic test doubles registered when `TESTING=1`. Test-only control endpoints under `/api/_test/...` let step definitions seed/clear adapter state without importing the backend in-process. New `UC3_steps.py` reuses UC1 building-setup and UC2 occupancy-seeding helpers.

### Part E) Traceability Table
See `docs/UC3/harness_design.md` Part E. Each of the 7 scenarios is mapped to its UI testids, DB tables touched, and service/adapter components.

## T3 — Implementation

### Files Created / Modified

**Backend (new):**
- `backend/app/domain/forecast.py` — domain types (`ForecastFeatures`, `ZoneForecast`, `ForecastRunResult`, `ForecastInputsMissing`).
- `backend/app/infrastructure/models/forecast_model.py` — `DemandForecastModel` SQLAlchemy mapping.
- `backend/app/infrastructure/repositories/forecast_repository.py` — `DemandForecastRepository` with `save_all`, `latest_for_building`, `count_for_building`.
- `backend/app/infrastructure/adapters/forecast_adapters.py` — `WeatherAdapter`/`DeviceStateAdapter`/`ForecastModelAdapter` Protocols, deterministic doubles, and a module-level `registry` swapped via `use_test_doubles()`.
- `backend/app/services/forecasting_service.py` — `ForecastService.run_forecast` (atomic) and `latest_for_building`.
- `backend/app/api/routes/forecasting.py` — `POST /api/buildings/{id}/forecasts/run` and `GET /api/buildings/{id}/forecasts/latest`.
- `backend/app/api/routes/test_support.py` — test-only `/api/_test/...` routes for seeding/clearing doubles and clearing per-zone occupancy.
- `backend/alembic/versions/1a325eb44672_uc3_demand_forecasts.py` — migration adding `demand_forecasts` table + `(zone_id, timestamp)` index.

**Backend (modified):**
- `backend/app/main.py` — included forecasting router; under `TESTING=1`, swap registry to doubles and mount test_support router.
- `backend/app/infrastructure/models/__init__.py` — export `DemandForecastModel`.
- `backend/app/infrastructure/repositories/occupancy_repository.py` — added `latest_for_zone(zone_id)`.

**Frontend (new):**
- `frontend/src/pages/ForecastPage/index.tsx` — `ForecastsPage` with building selector, run button, success/error panels, forecast table.

**Frontend (modified):**
- `frontend/src/types/index.ts` — added `ZoneForecast`, `ForecastRunResponse`.
- `frontend/src/services/api.ts` — added `runForecast`, `getLatestForecasts`.
- `frontend/src/App.tsx` — added `/forecasts` route.

**Tests (new / modified):**
- `tests/acceptance/steps/UC3_steps.py` — full step library (Background seeding, missing-input setup, action, assertions).
- `tests/acceptance/support/database_reset.py` — added `demand_forecasts` to truncate list.

### Acceptance Run

```bash
PYTHONPATH="./backend:." behave tests/acceptance/features/UC3_ForecastZoneDemand.feature
```

Result: **7 / 7 scenarios passed, 69 steps, 0 failed, 0.71s.** First-run pass — no T4 needed.

Full regression (UC1 + UC2 + UC3): **19 / 19 scenarios passed, 181 steps, 0 failed, 3.04s.**

---

## T4 — Failure Bundle and Patch
**Not invoked.** All UC3 scenarios passed on the first acceptance run, so no failure bundle was produced and no minimal patch was required. UC1 and UC2 continued to pass under the new schema.

---

## Finalization

- `feature_list.json` — UC3 status flipped to `pass` with evidence.
- `AGENT-PROGRESS.md` — updated with UC3 completion, decisions, and file list.
- Regression: 19 / 19 across UC1+UC2+UC3 (181 steps, 0 failures, 3.04s).
- Pending: commit + push (awaiting human approval per agent's hard rules).

