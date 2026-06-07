# UC7 DetectComfortViolationRisk — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`ComfortRiskService`** — `backend/app/services/comfort_risk_service.py`

Module constants:
```python
COMFORT_RISK_THRESHOLD = Decimal("0.5")
```

Public methods:
- `run(building_id: int) -> ComfortRiskRunResult`
- `latest_for_building(building_id: int) -> ComfortRiskRunResult | None`

`run` steps (all inside one `db` session, single commit at the end):
1. Load `BuildingModel` by id. Missing → raise `ComfortRiskInputsMissing(["building"])`.
2. Resolve `active_run_timestamp` via `SetpointRecommendationRepository.latest_run_timestamp_for_building(building_id)`. None → raise `ComfortRiskInputsMissing(["plan"])`.
3. Snapshot all latest-run recommendations by `zone_id` via `latest_rows_for_building(building_id, active_run_timestamp)`.
4. For each `zone` in `building.zones` ordered by `zone.id ASC`:
   - Get `setpoint_delta_f` from the recommendations snapshot. Missing → skip (A2).
   - Get the comfort-constraint row. Missing → record `missing_constraints += 1` and skip (A2).
   - Get `setpoint_f` from `DeviceStateAdapter.current_for_zone(zone.id)`. Missing → skip (A2).
   - Compute `projected`, `risk`, `direction`, `mitigation`. If `risk >= COMFORT_RISK_THRESHOLD`, append an `ComfortRiskAlert` candidate.
5. If **no zone** had constraints and **≥1 zone** was otherwise evaluable (had both delta + device state) → raise `ComfortRiskInputsMissing(["comfort_constraints"])` (S11 collapse case). Use a counter so a building where every zone is silently skipped due to missing **other** inputs still produces a `pass` row.
6. Build the `comfort_risk_runs` row (`decision`, `alerts_count`, `elapsed_ms`, `source_run_timestamp=active_run_timestamp`). Flush, capture `run_id`. Insert each `comfort_risk_alerts` row.
7. If `_force_db_error_flag` is set (test lever), raise `ComfortRiskForcedDbError` mid-write so the route maps to 500 and the transaction rolls back.
8. `db.commit()`. Log INFO.
9. Return `ComfortRiskRunResult(building_id, decision, alerts_count, source_run_timestamp, elapsed_ms, alerts)`.

Atomicity: any exception inside the try block → `db.rollback()` + re-raise.

### Domain types — `backend/app/domain/comfort_risk.py`
- `ComfortRiskAlert(zone_id, zone_name, projected_temp_f, occupied_min_f, occupied_max_f, risk_score, direction, mitigation)`.
- `ComfortRiskRunResult(building_id, decision, alerts_count, source_run_timestamp, elapsed_ms, alerts)`.
- `ComfortRiskInputsMissing(Exception)` with `missing_inputs: list[str]`.
- `ComfortRiskForcedDbError(Exception)` — test lever raised by the service when `force_db_error_next_run()` was called.

### Repositories
**`ComfortRiskRepository`** — `backend/app/infrastructure/repositories/comfort_risk_repository.py`
- `save_run(model: ComfortRiskRunModel) -> None` — add+flush, caller commits.
- `save_alerts(rows: list[ComfortRiskAlertModel]) -> None` — add_all+flush.
- `latest_for_building(building_id) -> ComfortRiskRunModel | None`.
- `alerts_for_run(run_id) -> list[ComfortRiskAlertModel]`.
- `count_runs_for_building(building_id) -> int`, `count_alerts_for_building(building_id) -> int`.

**`SetpointRecommendationRepository`** (extended)
- `latest_run_timestamp_for_building(building_id) -> datetime | None` — irrespective of applied state (A3).
- `latest_rows_for_building(building_id, run_timestamp) -> list[SetpointRecommendationModel]`.

### Adapter
No new adapter. The `DeviceStateAdapterDouble` now carries `setpoint_f` in its seeded payload (test endpoint extended, see Harness Part D). Production stub unchanged (UC7 acceptance does not need a real impl).

### API routes — `backend/app/api/routes/comfort_risk.py` (new; register in `main.py`)
- `POST /api/buildings/{building_id}/comfort-risk/run` → 200 `ComfortRiskRunResponse`, 400 `{detail:{missingInputs:[...]}}`, 500.
- `GET /api/buildings/{building_id}/comfort-risk/latest` → 200 `ComfortRiskRunResponse | null`.

### Wiring
`app.api.routes.comfort_risk.router` mounted in `main.py`.

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)
No change beyond extending the DB truncate (covered in `database_reset.py`).

### Test doubles
No new doubles. Reuses `WeatherAdapterDouble`, `DeviceStateAdapterDouble` (UC3), `OptimizationAdapterDouble` (UC4), `DeviceControlAdapterDouble` (UC5). The `DeviceStateAdapterDouble` already accepts arbitrary `payload` dicts (`{"on_count": 2, "setpoint_f": 72}` is just a richer payload).

### Test-only control endpoints (added to `app/api/routes/test_support.py`)
- `POST /api/_test/comfort_risk/force_db_error` → toggles `ComfortRiskService._FORCE_DB_ERROR_NEXT_RUN` so the next `run()` call raises mid-write.
- `POST /api/_test/recommendations/set_delta_for_zone` body `{zone_id, setpoint_delta_f}` — UPDATE the latest `setpoint_recommendations` row for the zone to the given delta. Used by S01–S07, S10, S12, S13, S14, S16.
- `POST /api/_test/recommendations/clear_for_zone` body `{zone_id}` — DELETE all `setpoint_recommendations` rows for the zone. Used by S10.

### Step definitions (`tests/acceptance/steps/UC7_steps.py`)
Reuses every UC3/UC4 background step. New UC7 steps:

| Step | Action |
|---|---|
| `Given the DeviceStateAdapter setpoint_f is set to N for every zone of "<bldg>"` | Re-seed each zone's device-state payload via `/api/_test/forecast_doubles` with `{"on_count":2,"setpoint_f":N}`. |
| `Given the latest recommendation setpoint_delta_f for zone "<zone>" of "<bldg>" is set to D` | POST `/api/_test/recommendations/set_delta_for_zone`. |
| `Given the latest recommendation rows for zone "<zone>" of "<bldg>" are deleted` | POST `/api/_test/recommendations/clear_for_zone`. |
| `Given the ComfortRiskService is configured to force a DB error on the next run for "<bldg>"` | POST `/api/_test/comfort_risk/force_db_error`. |
| `When the Scheduler triggers a comfort-risk run for "<bldg>"` | POST `/api/buildings/{id}/comfort-risk/run`. Stash response + elapsed. |
| `When the Scheduler triggers a comfort-risk run for "<bldg>" again` | Same POST; stash `context.second_response`. |
| `When the Scheduler triggers a comfort-risk run for an unknown building id` | POST against `9999999`. |
| `When the user triggers a comfort-risk run for "<bldg>" via the ComfortRiskPage` | Playwright drive `/comfort-risk`. |
| `Then the comfort-risk response has decision "<d>"` | assert 200 + body.decision. |
| `Then the comfort-risk response has alerts_count N` | body.alerts_count == N. |
| `Then the comfort-risk alert for zone "<zone>" of "<bldg>" has direction "<d>"` | scan body.alerts. |
| `Then the comfort-risk alert for zone "<zone>" of "<bldg>" has mitigation "<text>"` / `starting with "<prefix>"` | text equality / startswith. |
| `Then the comfort-risk alert for zone "<zone>" of "<bldg>" has risk_score "<s>"` | string equality after formatting. |
| `Then no comfort-risk alert exists for zone "<zone>" of "<bldg>"` | zone absent in body.alerts. |
| `Then the database contains N comfort_risk_runs rows for "<bldg>"` | GET `/comfort-risk/latest` returns 0/1 row; for N≥2, also call backend count endpoint. We use a SQL count via the existing test DB engine. |
| `Then the database contains N comfort_risk_alerts rows for "<bldg>"` | SQL count via test engine. |
| `Then the comfort-risk run is rejected with a missing-inputs error listing "<label>"` | assert 400 + label in `missingInputs`. |
| `Then the comfort-risk run returns a 500 server error` | assert 500. |
| `Then the comfort-risk run completes in under N milliseconds` | server `elapsed_ms` + client wall-clock. |
| `Then the two comfort-risk runs produce identical alert rows for "<bldg>"` | compare two response bodies' multiset of alert triples. |
| `Then the ComfortRiskPage shows the success banner` | Playwright. |
| `Then the ComfortRiskPage decision pill reads "<d>"` | Playwright. |
| `Then the ComfortRiskPage lists zone "<zone>" of "<bldg>" as an alert row` | Playwright `comfort-risk-alert-row-{id}`. |

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC7-S01 Above-band alert | n/a | 1 run, 1 alert | service computes risk, direction='above' |
| UC7-S02 Below-band alert | n/a | 1 run, 1 alert | direction='below', mitigation Increase |
| UC7-S03 Multi-zone mixed | n/a | 1 run, 2 alerts | partial filter |
| UC7-S04 All within band | n/a | 1 run, 0 alerts | decision='pass' |
| UC7-S05 Risk < 0.5 | n/a | 1 run, 0 alerts | threshold filter |
| UC7-S06 Risk = 0.5 | n/a | 1 run, 1 alert | threshold inclusive |
| UC7-S07 Mitigation text | n/a | 1 run, 2 alerts | A4 rounding |
| UC7-S08 Unknown building | n/a | 0 runs | building check |
| UC7-S09 No prior plan | n/a | 0 runs | plan check |
| UC7-S10 Partial plan | n/a | 1 run, alerts only for covered zones | A2 zone skip |
| UC7-S11 No constraints anywhere | n/a | 0 runs | collapse to 400 |
| UC7-S12 Missing device state | n/a | 1 run, no row for missing zone | A2 zone skip |
| UC7-S13 Cross-building | n/a | A=1 run, B=0 | building scoping |
| UC7-S14 Forced DB error | n/a | 0 runs, 0 alerts | transaction rollback |
| UC7-S15 Performance | n/a | 1 run | elapsed_ms < 3000 |
| UC7-S16 Determinism | n/a | 2 runs, identical alerts | deterministic compute |
| UC7-S17 UI flow | banner, pill, alert row | 1 run, 1 alert | `/comfort-risk` page |
