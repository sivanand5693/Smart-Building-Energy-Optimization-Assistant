# UC3 ForecastZoneDemand — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`ForecastService`** — `backend/app/services/forecast_service.py`

Public method: `run_forecast(building_id: int) -> ForecastRunResult`

Steps:
1. Load building + zones via `BuildingRepository`. If no zones → fail with `missingInputs=["zones"]`.
2. For each zone, fetch the latest `OccupancyRecord` via `OccupancyRepository.latest_for_zone(zone_id)`. Any zone with no record → fail with `missingInputs=["occupancy"]`.
3. Call `WeatherAdapter.current_for_building(building_id)`. Empty → `missingInputs=["weather"]`.
4. For each zone, call `DeviceStateAdapter.current_for_zone(zone_id)`. Any empty → `missingInputs=["device_state"]`.
5. If any of the above failed, raise `ForecastInputsMissing(missing_inputs=[...])` — caught by the route and rendered as `400` with structured JSON. **No DB writes occur.**
6. For each zone, build a feature dict (occupancy_count, weather_temp_c, device_on_count, ...) and call `ForecastModelAdapter.predict(zone_id, features) -> (predicted_kwh, model_version)`.
7. Within a single transaction, insert one `DemandForecastModel` row per zone using `DemandForecastRepository.save_all(rows)`.
8. Return `ForecastRunResult` with per-zone forecasts, run timestamp, and elapsed_ms.

### Domain types
- `ForecastFeatures` (immutable dataclass)
- `ZoneForecast` (zone_id, zone_name, timestamp, predicted_kwh, model_version)
- `ForecastRunResult` (building_id, run_timestamp, elapsed_ms, forecasts: list[ZoneForecast])
- `ForecastInputsMissing` exception (missing_inputs: list[str])

### Repository
**`DemandForecastRepository`** — `backend/app/infrastructure/repositories/demand_forecast_repository.py`
- `save_all(rows: list[DemandForecastModel]) -> None`
- `latest_for_building(building_id: int) -> list[DemandForecastModel]` (joins `zones` to scope by building, returns one row per zone — the row with the latest timestamp)

**`OccupancyRepository.latest_for_zone(zone_id)`** is a small extension to the UC2 repository.

### Adapters (test-doubled in acceptance)
- `WeatherAdapter` (interface) → `tests/acceptance/support/test_doubles/weather_adapter_double.py`
- `DeviceStateAdapter` (interface) → `tests/acceptance/support/test_doubles/device_state_adapter_double.py`
- `ForecastModelAdapter` (interface) → `tests/acceptance/support/test_doubles/forecast_model_double.py`

Production adapters are **not** required for UC3 to pass (per A1–A3); placeholder real implementations may raise `NotImplementedError`.

### API route
`backend/app/api/routes/forecast.py`
- `POST /api/buildings/{id}/forecasts/run` → calls `ForecastService.run_forecast`. 200 on success, 400 with `{detail: {missingInputs: [...]}}` on `ForecastInputsMissing`.
- `GET /api/buildings/{id}/forecasts/latest` → calls `DemandForecastRepository.latest_for_building`. 200 with array of zone forecasts (possibly empty).

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)

`before_all` (extend existing):
- After backend subprocess starts, register a request to bind the doubles: the harness exposes a *control endpoint* `POST /api/_test/forecast_doubles` (only mounted when `TESTING=1`) that lets the harness inject seeded values into in-process double stores. Alternative considered: monkey-patching via dependency-injection container at app start. Going with the control-endpoint approach — keeps acceptance clear of in-process imports and matches how UC2 tests interact with the running backend.

`before_scenario`:
- Existing DB reset truncates `demand_forecasts` (added to truncate list).
- Reset all adapter doubles to a known-empty state via `POST /api/_test/forecast_doubles/reset`.

`after_scenario`:
- No additional cleanup beyond what UC1/UC2 already do.

### Test doubles

**`WeatherAdapterDouble`**
- In-memory dict `building_id → weather_payload`.
- `seed(building_id, payload)`, `clear(building_id)`, `current_for_building(building_id) -> dict | None`.

**`DeviceStateAdapterDouble`**
- In-memory dict `zone_id → device_state_payload`.
- `seed(zone_id, payload)`, `clear(zone_id)`, `current_for_zone(zone_id) -> dict | None`.

**`ForecastModelDouble`**
- Deterministic: `predict(zone_id, features) → (predicted_kwh, model_version)` returns `(zone_id * 1.5 + features["occupancy_count"] * 0.1, "double-1.0")`. Stable across runs so assertions can match exact values if needed.

The doubles are registered in `backend/app/main.py` via a feature flag (`TESTING=1`) — when set, the dependency-injection wiring substitutes the doubles for the production adapter classes and mounts the control router under `/api/_test`.

### Step definitions (`tests/acceptance/steps/UC3_steps.py`)

Reuses the UC1 building-creation helpers and UC2 occupancy seeding. New steps:

- `Given the WeatherAdapter is seeded with current weather for "<building>"` → POST to `/api/_test/forecast_doubles` with payload `{kind: "weather", building_id, payload: {...}}`.
- `Given the DeviceStateAdapter is seeded with current device state for every zone of "<building>"` → loops over zones, POSTs per zone.
- `Given the ForecastModelAdapter test double returns deterministic predictions` → no-op (default state).
- `Given the latest occupancy snapshot is missing for zone "<zone>" of "<building>"` → POSTs `/api/_test/clear_occupancy_for_zone`.
- `Given the WeatherAdapter has no data for "<building>"` → POSTs the clear endpoint.
- `Given the DeviceStateAdapter has no data for zone "<zone>" of "<building>"` → POSTs the clear endpoint.
- `Given a previous successful forecast run exists for "<building>" with N forecast rows` → triggers a normal seeded run, asserts 200 and N rows, then continues with scenario.
- `When the Scheduler triggers a forecast run for "<building>"` → POST `/api/buildings/{id}/forecasts/run`; capture status, body, elapsed time.
- `Then the run result lists N zone forecasts` → assert response body length.
- `Then each zone forecast exposes a non-null timestamp and zone_id` → assert per-row keys.
- `Then the database contains N demand_forecast rows for "<building>"` → assert via `GET /api/buildings/{id}/forecasts/latest` length (acceptance treats the read API as the persistence oracle — same pattern as UC1/UC2).
- `Then the ForecastsPage displays N forecast rows for "<building>"` → Playwright: visit `/forecasts`, select building, count `forecast-row-*` testids.
- `Then the run is rejected with a missing-inputs error listing "<input>"` → assert 400 status and `detail.missingInputs` includes the value.
- `Then the forecast run completes in under N milliseconds` → assert captured elapsed_ms < N.
- `Then every persisted demand_forecast row has a non-null timestamp column` / `... a zone_id referencing an existing zone` → assert via `latest` API + cross-check zone existence in `GET /api/buildings`.
- `Then the database still contains N demand_forecast rows for "<building>" from the prior run` → same persistence-oracle as above.

### Test-only control endpoints

Mounted only when `TESTING=1`:
- `POST /api/_test/forecast_doubles` — `{kind: "weather"|"device_state"|"forecast_model", building_id?, zone_id?, payload}` — seeds.
- `POST /api/_test/forecast_doubles/clear` — `{kind, building_id?, zone_id?}` — clears one entry.
- `POST /api/_test/forecast_doubles/reset` — clears everything.
- `POST /api/_test/clear_occupancy_for_zone` — `{zone_id}` — deletes rows from `occupancy_records` for that zone.

These endpoints are **not** registered when `TESTING` is unset — they cannot leak into a non-test build.

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC3-S01 Successful forecast | building selector, run button, forecast-table, forecast-row-{id} | `demand_forecasts` (3 rows), `zones` (read), `occupancy_records` (read) | `ForecastService.run_forecast`, all 3 adapter doubles |
| UC3-S02 Missing occupancy | run button, run-error panel, missing-inputs list | `demand_forecasts` (0 rows), `occupancy_records` (one zone empty) | `ForecastService` precondition check on occupancy |
| UC3-S03 Missing weather | run-error panel, missing-inputs list | `demand_forecasts` (0 rows) | `WeatherAdapterDouble` cleared |
| UC3-S04 Missing device-state | run-error panel, missing-inputs list | `demand_forecasts` (0 rows) | `DeviceStateAdapterDouble` cleared for one zone |
| UC3-S05 Structured fields | none beyond default render | `demand_forecasts.timestamp`, `demand_forecasts.zone_id` | `DemandForecastRepository.latest_for_building` |
| UC3-S06 Performance | none | none direct | `ForecastService` end-to-end timing captured by harness |
| UC3-S07 Atomicity | none beyond default | `demand_forecasts` row count unchanged | `ForecastService` rollback on missing input |
