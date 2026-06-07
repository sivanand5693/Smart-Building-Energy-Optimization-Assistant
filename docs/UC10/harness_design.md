# UC10 HandleSensorDataOutage — Harness Design

## Part C — Service Contract

### Domain types (`backend/app/domain/sensor_outage.py`)

```python
@dataclass
class SensorOutageResult:
    event_id: Optional[int]
    building_id: int
    affected_zone_ids: list[int]
    decision: str        # 'fallback' | 'paused'
    notes: str
    degraded_forecast_zone_ids: list[int]
    degraded_recommendation_ids: list[int]
    elapsed_ms: float
    declared_at: Optional[datetime] = None


class SensorOutageInputsMissing(Exception):
    def __init__(self, missing_inputs: list[str]): ...


class SensorOutageForcedDbError(Exception):
    """Test lever for S11 — service raises mid-write."""
```

### Service (`backend/app/services/sensor_outage_service.py`)

`SensorOutageService.handle(building_id: int, affected_zone_ids: list[int], reason: str) -> SensorOutageResult`

1. Validate inputs:
   - `building_id` resolves to a `BuildingModel` row, else `SensorOutageInputsMissing(['building'])`.
   - `affected_zone_ids` non-empty, else `['affected_zone_ids']`.
   - `reason` (after `.strip()`) non-empty, else `['reason']`.
   - Every element of `affected_zone_ids` belongs to the building's zone set, else `['zone']`.
   - Labels deduplicated + sorted alphabetically when accumulating multiple gaps.
2. Apply decision rule (A1):
   - Pull `affected_zone_ids ⊆ all_zone_ids_of_building`?
   - For every affected zone, probe `demand_forecasts` for any row with `created_at >= now() - INTERVAL '24 hours'`.
   - `paused` iff (affected == all_zones) AND (no recent forecast for any affected zone).
   - Else `fallback`.
3. If `fallback`:
   - For each `zone_id` in `affected_zone_ids`: call `DemandForecastRepository.mark_latest_degraded_for_zone(zone_id)` (no-commit). Collect the zone ids where a row was updated → `degraded_forecast_zone_ids`.
   - Call `SetpointRecommendationRepository.mark_latest_run_degraded_for_zones(building_id, affected_zone_ids)` (no-commit). Returns the list of recommendation ids updated → `degraded_recommendation_ids`.
4. Compose `notes`:
   - `fallback`: `notes = reason`.
   - `paused`: `notes = reason + " | no recent forecast for any zone — planning paused"`.
5. Consume the test lever — if set, raise `SensorOutageForcedDbError` before commit.
6. Build a `SensorOutageEventModel` row carrying the fields; `repo.save_no_commit(row)`; `db.commit()`.
7. Log: `logger.info("sensor_outage_handled building_id=... decision=... affected_zone_ids=...")` (A4).
8. Return `SensorOutageResult` with measured `elapsed_ms`.

On any unexpected exception: `db.rollback()` and re-raise. The route catches `SensorOutageInputsMissing` → 400, `SensorOutageForcedDbError` → 500 with `{"error":"db_error"}`, `Exception` → 500 with `{"error":"sensor_outage_error"}`.

### Repository (`backend/app/infrastructure/repositories/sensor_outage_repository.py`)

```
class SensorOutageRepository:
    def save_no_commit(row: SensorOutageEventModel) -> None
    def list_for_building(building_id: int) -> list[SensorOutageEventModel]
        # ORDER BY declared_at DESC, id DESC
    def count_for_building(building_id: int) -> int
```

### Repository extensions

- `DemandForecastRepository.mark_latest_degraded_for_zone(zone_id: int) -> int | None`
  - SELECT the latest `demand_forecasts` row for `zone_id` (ORDER BY `created_at DESC, id DESC` LIMIT 1).
  - If found and `degraded_confidence is false`, UPDATE it; else no-op.
  - Returns the updated id, or `None` when there's nothing to flag.
  - No commit.
- `SetpointRecommendationRepository.mark_latest_run_degraded_for_zones(building_id: int, zone_ids: list[int]) -> list[int]`
  - SELECT MAX(`run_timestamp`) for `(building_id, zone_id IN zone_ids)`. If none, return `[]`.
  - UPDATE `setpoint_recommendations SET degraded_confidence = true WHERE building_id = :b AND run_timestamp = :ts AND zone_id IN :ids`.
  - Returns the list of row ids updated.
  - No commit.

### Route (`backend/app/api/routes/sensor_outage.py`)

- `POST /api/sensors/outage/handle` with body `SensorOutageHandleRequest(building_id, affected_zone_ids, reason)` → `SensorOutageResponse`.
- `GET /api/buildings/{building_id}/sensor-outages` → `list[SensorOutageEventResponse]` ordered by `declared_at DESC`.

### Cross-UC additive changes (A10)

- `backend/app/api/routes/forecasting.py::ZoneForecastOut` gains `degraded_confidence: bool = False`. `ForecastService.latest_for_building` reads the model column; `run_forecast` returns `False` (the column default).
- `backend/app/api/routes/recommendations.py::RecommendationOut` gains `degraded_confidence: bool = False`. `RecommendationService.latest_for_building` reads the model column; `run` returns `False`.
- Both domain dataclasses (`ZoneForecast`, `RankedRecommendation`) gain a `degraded_confidence: bool = False` field so the response builders can copy without `getattr`.
- Frontend types `ZoneForecast` and `SetpointRecommendation` gain `degraded_confidence?: boolean` (optional in TS to keep callers happy).
- Frontend pages `/forecasts` and `/recommendations` render `degraded-badge-{zone_id}` when `degraded_confidence === true`.

This is the **one cross-UC touch**. We do **not** modify UC3/UC4 business logic, feature files, or step definitions.

## Part D — Test Doubles & Test-Support Surface

### Test-support endpoints (mounted only when `TESTING=1`)

- `POST /api/_test/sensor_outage/force_db_error` → arms the next service call to raise `SensorOutageForcedDbError`. Mirrors UC8/UC9 levers.
- `POST /api/_test/forecasts/seed_for_zone` body `{zone_id, predicted_kwh?, model_version?, hours_ago?}` → inserts a `demand_forecasts` row, with `created_at = now() - hours_ago * INTERVAL '1 hour'`. Default `hours_ago=0`, `predicted_kwh=10.000`, `model_version="test-v0"`.
- `POST /api/_test/recommendations/seed_for_zone` body `{building_id, zone_id, setpoint_delta_f?, projected_savings_kwh?, comfort_impact?, rank?, run_timestamp?}` → inserts a `setpoint_recommendations` row. Default `setpoint_delta_f=-1.0`, `projected_savings_kwh=5.000`, `comfort_impact='none'`, `rank=1`, `run_timestamp=now()`.

These seeders let the steps create UC10 inputs without dragging the full UC3/UC4 fixture chains in.

### No new adapter doubles needed

UC10 has no external adapter calls. The only test lever is the in-process `force_db_error` flag.

### Steps file (`tests/acceptance/steps/UC10_steps.py`)

Reuses `the system is initialized for acceptance testing` and `a building "..." exists with zones` from UC3's step file (auto-discovered by behave).

New steps:

- `Given a recent demand_forecasts row exists for zone "..." of "..."` — POSTs to `/api/_test/forecasts/seed_for_zone` with `hours_ago=0`.
- `Given a latest-run setpoint_recommendations row exists for zone "..." of "..."` — POSTs to `/api/_test/recommendations/seed_for_zone`.
- `Given two demand_forecasts rows exist for zone "..." of "..." — an older one and a newer one` — POSTs twice with `hours_ago=48` then `hours_ago=0`.
- `Given the SensorOutageService is configured to force a DB error on the next request` — POSTs to `/api/_test/sensor_outage/force_db_error`.
- `When the MonitoringService declares a sensor outage for "..." affecting zones "..." with reason "..."` — POSTs to `/api/sensors/outage/handle`.
- `When the MonitoringService declares a sensor outage for unknown building id ... affecting zones "..." with reason "..."`.
- `When the MonitoringService declares a sensor outage for "..." affecting no zones with reason "..."`.
- `When the MonitoringService declares a sensor outage for "A" affecting zone of "B" "..." with reason "..."` — picks a zone from a different building.
- `When the FacilityManager fetches the latest forecasts for "..."`.
- `When the FacilityManager fetches the latest recommendations for "..."`.
- `When the FacilityManager fetches the sensor outage history for "..."`.
- `Then the sensor outage response status is N`.
- `Then the sensor outage response has decision "..."`.
- `Then the sensor outage response missingInputs equals [...]`.
- `Then the sensor outage response elapsed_ms is under N`.
- `Then the latest demand_forecasts row for zone "..." of "..." has degraded_confidence "true|false"`.
- `Then the newest|oldest demand_forecasts row for zone "..." of "..." has degraded_confidence "..."`.
- `Then the latest-run setpoint_recommendations rows for zone "..." of "..." have degraded_confidence "..."`.
- `Then the database contains N sensor_outage_events row[s] for "..."`.
- `Then the sensor_outage_events row notes for "..." contain "..."`.
- `Then the latest forecasts response carries degraded_confidence "..." for zone "..." of "..."`.
- `Then the latest recommendations response carries degraded_confidence "..." for zone "..." of "..."`.
- `Then the sensor outage history has N events`.
- `Then the sensor outage history first event reason equals "..."`.
- UI: `When the user declares a sensor outage for "..." affecting zones "..." with reason "..." via the SensorOutagePage`; `Then the SensorOutagePage shows ...`; `When the user opens the /forecasts page for "..."`; etc.

## Part E — Acceptance Oracle Mapping

| # | Scenario | Oracle | Key assertion |
|---|---|---|---|
| S01 | Happy fallback (1 zone) | persistence + fallback flag | `decision='fallback'`; flagged forecast + rec rows; 1 event row |
| S02 | Multi-zone fallback | isolation | only `Z1, Z2` flagged; `Z3` rows still `false` |
| S03 | Pause | pause oracle | `decision='paused'`; zero flag updates; event row notes contain "planning paused" |
| S04 | All zones, recent forecast | fallback | `decision='fallback'` (rule A1 — recent forecast for `Lobby` blocks pause) |
| S05 | DB persistence — older row untouched | isolation | newest row flagged true; oldest row stays false |
| S06 | Non-idempotent re-declare | persistence | two event rows; flag stays true |
| S07 | Unknown building | missing-inputs | `missingInputs=["building"]` |
| S08 | Empty `affected_zone_ids` | missing-inputs | `missingInputs=["affected_zone_ids"]` |
| S09 | Cross-building zone id | missing-inputs | `missingInputs=["zone"]` |
| S10 | Missing reason | missing-inputs | `missingInputs=["reason"]` |
| S11 | Atomicity | atomicity | 500; zero new event rows; flag preserved |
| S12 | Cross-building isolation | isolation | B's row stays `false`; only A has an event |
| S13 | Performance | Q2 | `elapsed_ms < 2000` |
| S14 | UC3 surface | UC3 surface | `GET /forecasts/latest` returns `degraded_confidence=true` for the flagged zone |
| S15 | UC4 surface | UC4 surface | `GET /recommendations/latest` returns `degraded_confidence=true` for the flagged zone |
| S16 | History endpoint | history | newest first by `declared_at DESC` |
| S17 | UI flow | UI | decision pill `fallback`; affected-zone chip; history row; degraded badges on `/forecasts` and `/recommendations` |
