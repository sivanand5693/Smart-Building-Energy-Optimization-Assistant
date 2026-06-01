# UC4 RecommendHVACSetpointChanges — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`RecommendationService`** — `backend/app/services/recommendation_service.py`

Public methods:
- `run(building_id: int) -> RecommendationRunResult`
- `latest_for_building(building_id: int) -> list[RankedRecommendation]`

`run` steps:
1. Load `BuildingModel` by id. Missing -> raise `RecommendationInputsMissing(["building"])`.
2. Load `building.zones`. Empty -> `RecommendationInputsMissing(["zones"])`.
3. For each zone, load the latest `DemandForecastModel` via `DemandForecastRepository.latest_for_zone`. Missing for any zone, **or** `(now - timestamp) > 24h` for any zone -> `RecommendationInputsMissing(["forecast"])`.
4. For each zone, load `ZoneComfortConstraintModel`. Missing for any zone -> `RecommendationInputsMissing(["comfort_constraints"])`.
5. For each zone, call `OptimizationAdapter.recommend(zone_id, forecast, constraints)` -> `list[Candidate]`.
6. Filter candidates: `new_setpoint = midpoint(occupied_min_f, occupied_max_f) + setpoint_delta_f` must lie within `[min_setpoint_f, max_setpoint_f]`.
7. Sort surviving candidates across all zones: key = `(-projected_savings_kwh, zone_id, setpoint_delta_f)`. Assign `rank = 1..K`.
8. Persist as `SetpointRecommendationModel` rows in one transaction via `SetpointRecommendationRepository.save_all(rows)`.
9. Return `RecommendationRunResult(building_id, run_timestamp, elapsed_ms, recommendations=...)`.

### Domain types (in `backend/app/domain/recommendation.py`)
- `Candidate(setpoint_delta_f, projected_savings_kwh, comfort_impact, model_version)` — adapter output.
- `RankedRecommendation(building_id, zone_id, zone_name, run_timestamp, setpoint_delta_f, projected_savings_kwh, comfort_impact, rank, model_version)`.
- `RecommendationRunResult(building_id, run_timestamp, elapsed_ms, recommendations: list[RankedRecommendation])`.
- `RecommendationInputsMissing(Exception)` with `missing_inputs: list[str]`.

### Repository
**`SetpointRecommendationRepository`** — `backend/app/infrastructure/repositories/recommendation_repository.py`
- `save_all(rows: list[SetpointRecommendationModel]) -> None`
- `latest_for_building(building_id: int) -> list[SetpointRecommendationModel]` — rows of the most recent `run_timestamp` for the building, ordered by `rank ASC`.
- `count_for_building(building_id: int) -> int`

**`ZoneComfortConstraintRepository`** — same file or sibling
- `for_zone(zone_id) -> ZoneComfortConstraintModel | None`
- `upsert(constraint)` (used by the test-only seed endpoint).

`DemandForecastRepository.latest_for_zone(zone_id)` — small addition reused from UC3 plumbing.

### Adapter
`OptimizationAdapter` Protocol in `backend/app/infrastructure/adapters/optimization_adapter.py`:
```
class OptimizationAdapter(Protocol):
    def recommend(
        self,
        zone_id: int,
        forecast: DemandForecastModel,
        constraints: ZoneComfortConstraintModel,
    ) -> list[Candidate]: ...
```
Production stub raises `NotImplementedError` (UC4 deferred — see A3). Test double mounted when `TESTING=1`.

### API routes
`backend/app/api/routes/recommendations.py`:
- `POST /api/buildings/{id}/recommendations/run` -> 200 on success, 400 `{detail:{missingInputs:[...]}}` on `RecommendationInputsMissing`.
- `GET /api/buildings/{id}/recommendations/latest` -> 200 with array (possibly empty) ordered by `rank ASC`.

### Wiring
Mount the new router in `backend/app/main.py`. The optimization adapter is wired in the existing `forecast_adapters.registry` extension or in a sibling registry; we extend the existing `registry` so a single startup hook activates all doubles.

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)
No change needed beyond the existing DB truncate (UC4 just adds two tables to the existing list — handled in `database_reset.py`).

### Test doubles
**`OptimizationAdapterDouble`** — `tests/acceptance/support/test_doubles/optimization_adapter_double.py` (note: the production-side double is colocated with the adapter module to enable in-process wiring on `use_test_doubles()`).

Behavior:
- For each zone, by default emits exactly one candidate `(setpoint_delta_f = +1.0, projected_savings_kwh = zone_id * 1.0 + 0.5, comfort_impact = "minor", model_version = "opt-double-1.0")`. Choosing `+1.0` keeps `new_setpoint = 71.5 + 1.0 = 72.5` inside `[65, 78]` so every default candidate is feasible.
- `force_infeasible(zone_id)` flips that zone's delta to `+50.0` so `new_setpoint = 121.5 > 78` and the candidate is filtered (S07).
- `reset()` clears any forced state.

### Test-only control endpoints
Extend the existing `app/api/routes/test_support.py`:
- `POST /api/_test/comfort_constraints/seed` `{zone_id, min_setpoint_f?, max_setpoint_f?, occupied_min_f?, occupied_max_f?, unoccupied_min_f?, unoccupied_max_f?}` — upserts a constraints row using defaults for any missing field.
- `POST /api/_test/comfort_constraints/clear` `{zone_id}` — deletes the constraints row for a zone.
- `POST /api/_test/forecasts/force_stale` `{zone_id, hours_old}` — back-dates the latest `demand_forecasts.timestamp` for a zone.
- `POST /api/_test/forecasts/clear_for_zone` `{zone_id}` — deletes `demand_forecasts` rows for a zone (for "forecast missing" scenarios).
- `POST /api/_test/optimization_double/force_infeasible` `{zone_id}` — toggles the double's infeasible-output mode for a zone.
- `POST /api/_test/optimization_double/reset` — clears all forced state.

These are mounted only when `TESTING=1`.

### Step definitions (`tests/acceptance/steps/UC4_steps.py`)
Reuses every UC3 step (building seeding, occupancy seeding, weather/device-state doubles, the `forecasting_doubles/reset` cycle). New UC4 steps:

| Step | Action |
|---|---|
| `Given a fresh demand forecast exists for every zone of "<building>"` | POST `/api/buildings/{id}/forecasts/run` (UC3 endpoint); assert 200 |
| `Given default comfort constraints are seeded for every zone of "<building>"` | Loop zones, POST `/api/_test/comfort_constraints/seed` |
| `Given the OptimizationAdapter test double returns deterministic recommendations` | POST `/api/_test/optimization_double/reset` |
| `Given the OptimizationAdapter test double is configured to emit an infeasible candidate for zone "<zone>" of "<building>"` | POST `/api/_test/optimization_double/force_infeasible` |
| `Given the latest demand forecast is missing for zone "<zone>" of "<building>"` | POST `/api/_test/forecasts/clear_for_zone` |
| `Given the latest demand forecast for zone "<zone>" of "<building>" is forced to <N> hours old` | POST `/api/_test/forecasts/force_stale` |
| `Given the comfort constraints for zone "<zone>" of "<building>" are deleted` | POST `/api/_test/comfort_constraints/clear` |
| `Given a previous successful recommendation run exists for "<building>" with <N> recommendation rows` | POST the run endpoint; assert 200 and N rows |
| `When the FacilityManager triggers a recommendation run for "<building>"` | POST `/api/buildings/{id}/recommendations/run`; capture body, status, elapsed |
| `When the FacilityManager triggers a recommendation run for an unknown building id` | POST with id `9_999_999` |
| `When the ranked recommendations are captured as the baseline` | snapshot the response rows |
| `When the user triggers a recommendation run for "<building>" via the RecommendationsPage` | Playwright drive |
| `Then the run result lists <N> recommendation rows` | assert response 200 + length |
| `Then each recommendation row exposes building_id, zone_id, ...` | assert keys present and non-null |
| `Then the database contains <N> setpoint_recommendation rows for "<building>"` | GET `/latest`, assert length |
| `Then the database still contains <N> setpoint_recommendation rows for "<building>" from the prior run` | same as above (preservation) |
| `Then the RecommendationsPage displays <N> recommendation rows for "<building>"` | Playwright count of `recommendation-row-*` |
| `Then no recommendation row references zone "<zone>" of "<building>"` | GET `/latest`, assert no row has matching zone_id |
| `Then the projected_savings_kwh sequence over the ranked rows is monotonically non-increasing` | iterate rows, assert pairwise |
| `Then every recommendation row has a projected_savings_kwh greater than or equal to 0` | iterate rows |
| `Then every recommendation row has a comfort_impact in "<csv>"` | parse csv, iterate |
| `Then the ranked recommendations match the baseline exactly` | compare snapshot tuples |
| `Then the recommendation run completes in under <N> milliseconds` | assert server `elapsed_ms` and client wall-clock |
| `Then the run is rejected with a missing-inputs error listing "<label>"` | assert 400 + `missingInputs` contains label |
| `Then the RecommendationsPage shows an error banner listing "<label>"` | Playwright wait for `recommendation-run-error` + assert label in `recommendation-missing-inputs` |
| `Then the RecommendationsPage displays no recommendation rows for "<building>"` | Playwright count == 0 |
| `Then the RecommendationsPage run button is re-enabled` | Playwright assert `recommendation-run-button` not disabled |

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC4-S01 Happy 3-zone | selector, run button, table, rows | `setpoint_recommendations` (3 rows), `zone_comfort_constraints`, `demand_forecasts` (read) | `RecommendationService.run`, `OptimizationAdapterDouble` x3 |
| UC4-S02 Single zone | none beyond default | 1 row | same as S01 with 1 zone |
| UC4-S03 6-zone | none beyond default | 6 rows | same as S01 with 6 zones |
| UC4-S04 Ranking monotonic | none | row sequence | service ranking step |
| UC4-S05 Savings >= 0 | none | row values | service ranking step + adapter contract |
| UC4-S06 comfort_impact enum | none | row values | adapter contract + DB CHECK |
| UC4-S07 Infeasible filtered | none | 2 rows (instead of 3) | service feasibility filter |
| UC4-S08 Missing forecast | none | 0 rows | service forecast check |
| UC4-S09 Stale forecast | none | 0 rows | service staleness check (24h) |
| UC4-S10 Missing constraints | none | 0 rows | service constraints check |
| UC4-S11 Unknown building | none | 0 rows | service building check |
| UC4-S12 Empty building | none | 0 rows | service zones check |
| UC4-S13 Prior preserved | none | rows unchanged | service rollback on failure |
| UC4-S14 Cross-building isolation | none | B's rows untouched | service transaction scope |
| UC4-S15 Determinism | none | identical rows | deterministic double |
| UC4-S16 Performance | none | none direct | service end-to-end timing |
| UC4-S17 UI error gating | error banner, missing-inputs, run-button re-enabled | 0 rows | service constraints check + page lifecycle |
