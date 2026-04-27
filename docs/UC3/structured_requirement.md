# UC3 ForecastZoneDemand — Structured Requirement

## A) Structured Requirement

**Use case name:** ForecastZoneDemand

**Participating actors:**
- Scheduler (primary, initiates)
- Forecasting Service (control)
- Optimization Service (downstream consumer — out of scope here, only stored output is verified)

**Goal:** Produce and persist a zone-level energy demand forecast for every zone of a building, using current occupancy, weather, and device-state inputs, so that the Optimization Service can consume up-to-date demand estimates.

**Preconditions:**
- A building profile with at least one zone exists (UC1).
- An occupancy schedule for that building exists (UC2).
- Current weather data for the building location is available.
- Current device-state data for the building's zones is available.

**Main success flow:**
1. Scheduler triggers `ForecastZoneDemand` for a target building.
2. System retrieves the building's zones.
3. System retrieves the latest occupancy snapshot per zone (from `occupancy_records`).
4. System retrieves current weather for the building location (via WeatherAdapter).
5. System retrieves current device state for each zone (via DeviceStateAdapter).
6. System invokes the forecasting model (via ForecastModelAdapter) for each zone with the gathered features.
7. System stores one `demand_forecast` row per zone, each containing `zone_id`, `timestamp`, `predicted_kwh`, `model_version`, and `created_at`.
8. System returns a structured run result listing per-zone forecasts and the total processing time.

**Success postconditions:**
- A new `demand_forecast` row exists per zone for the run timestamp.
- The run result is observable via API (`GET /api/buildings/{id}/forecasts/latest`).
- Total processing time for the run is recorded.

**Failure postconditions:**
- No `demand_forecast` rows are persisted for the run (atomic — all or nothing).
- A structured error identifies the missing input(s): occupancy / weather / device state.
- The building's previously stored forecasts (from prior runs) remain untouched.

**Quality requirements:**
- Q1: Each forecast record exposes `timestamp` and `zone_id` as structured fields.
- Q2: A forecast run for a building with up to 10 zones completes in under **6000 ms** end-to-end.
- Q3: Forecasts are atomic per run — partial persistence is forbidden.

**Assumptions:**
- **A1:** The forecasting model is encapsulated behind a `ForecastModelAdapter` interface. Acceptance runs use a deterministic test double (`tests/acceptance/support/test_doubles/forecast_model_double.py`) that returns known kWh values per zone. A real scikit-learn-backed adapter may be added later but is not required to pass the contract.
- **A2:** Weather data is encapsulated behind a `WeatherAdapter` interface. Acceptance runs use a deterministic test double seeded per scenario. Real weather-API integration is out of scope for UC3.
- **A3:** Device-state data is encapsulated behind a `DeviceStateAdapter` interface. Acceptance runs use a deterministic test double. Real BMS/IoT integration is out of scope.
- **A4:** Although the spec says "Scheduler triggers", the acceptance contract exercises the trigger via an HTTP endpoint `POST /api/buildings/{id}/forecasts/run`. Production scheduling (cron / Celery / APScheduler) is **deferred** and out of scope for UC3. The endpoint is the testable boundary.
- **A5:** A minimal viewer surface is provided (`ForecastsPage` listing latest forecasts per zone for a selected building) so the run is observable in the UI for acceptance scenarios. No editing UI is needed.
- **A6:** "Missing input data" means: the building has no zones, or the latest occupancy snapshot is missing for at least one zone, or the WeatherAdapter returns no data, or the DeviceStateAdapter returns no data for at least one zone. In all such cases the run fails atomically.
- **A7:** `model_version` is a string captured from the adapter at forecast time so retrospective audits can identify which model produced a given forecast.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check |
|---|---|
| Scheduler triggers forecast | `POST /api/buildings/{id}/forecasts/run` returns 200 with structured run result |
| System gathers occupancy data | Service queries latest occupancy per zone before invoking model |
| System gathers weather data | Service calls WeatherAdapter before invoking model |
| System gathers device-state data | Service calls DeviceStateAdapter before invoking model |
| System runs forecasting model per zone | Model adapter invoked once per zone in the building |
| System stores forecasts with timestamps + zone IDs | One `demand_forecast` row per zone, each with non-null `timestamp` and `zone_id` |
| Forecasts available to Optimization Service | `GET /api/buildings/{id}/forecasts/latest` returns the run's per-zone forecasts |
| Missing input data is reported | When any required input is missing, response is 400 with structured error and no rows are persisted |
| Performance budget | Run for ≤10 zones completes in < 6000 ms |
| Structured fields | Each forecast row exposes `timestamp` and `zone_id` as queryable columns |

## C) Acceptance Oracles

- **UI oracle:** ForecastsPage lists per-zone rows with `zone_name`, `predicted_kwh`, and `timestamp` after a successful run.
- **Persistence oracle:** `demand_forecast` table contains exactly one row per zone for the latest run.
- **Atomicity oracle:** On failure, `demand_forecast` row count for the building is unchanged from before the run.
- **Field-structure oracle:** Each forecast row has a non-null `timestamp` and a `zone_id` referencing an existing zone.
- **Performance oracle:** Run wall-clock time recorded by the harness is < 6000 ms.
- **Error oracle:** On missing input, response body includes a `missingInputs` array naming which adapters/datasets were unavailable.
