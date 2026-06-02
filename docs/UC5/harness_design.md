# UC5 ApplyApprovedEnergyPlan — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`ApplyPlanService`** — `backend/app/services/apply_plan_service.py`

Public methods:
- `apply(building_id: int, recommendation_ids: list[int]) -> ApplyPlanRunResult`
- `latest_for_building(building_id: int) -> list[AppliedChange]`

`apply` steps:
1. Load `BuildingModel` by id. Missing → raise `ApplyInputsMissing(["building"])`.
2. Load all `setpoint_recommendations` rows whose ids ∈ `recommendation_ids`. If any id is not found at all, **or** any found row's `building_id` ≠ the target building → raise `ApplyInputsMissing(["recommendation"])`.
3. Compute the latest `run_timestamp` for the target building from `setpoint_recommendations`. If any approved row's `run_timestamp` ≠ latest → raise `ApplyInputsMissing(["stale_run"])`.
4. Sort approved rows by `rank ASC` to determine dispatch order.
5. For each approved rec, in rank order:
   1. Look up the first HVAC device for the zone via `DeviceRepository.first_hvac_for_zone(zone_id)`. If `None` → append `AppliedSetpointChangeModel(status='failed', error_code='missing_device', adapter_message='no HVAC device', latency_ms=0)` to the pending batch.
   2. Else check `AppliedChangeRepository.exists_for_recommendation(rec.id)`. If True → append `failed`/`already_applied`. **Skip adapter call.**
   3. Else call `registry.device_control.dispatch(device_id, zone_id, setpoint_delta_f, run_timestamp, recommendation_id)`. The adapter returns `DispatchOutcome(status, error_code, adapter_message, latency_ms)`. Append the matching row.
6. After loop, `repo.save_all(rows)` inside one transaction. On `SQLAlchemyError` → rollback, re-raise so the route returns 500.
7. Return `ApplyPlanRunResult(building_id, applied_at, elapsed_ms, results=[...])`.

### Domain types — `backend/app/domain/applied_change.py`
- `DispatchOutcome(status, error_code, adapter_message, latency_ms)` — adapter return.
- `AppliedChange(recommendation_id, building_id, zone_id, applied_at, setpoint_delta_f, status, error_code, adapter_message, latency_ms)` — service-level view.
- `ApplyPlanRunResult(building_id, applied_at, elapsed_ms, results: list[AppliedChange])`.
- `ApplyInputsMissing(Exception)` with `missing_inputs: list[str]`.

### Repository
**`AppliedChangeRepository`** — `backend/app/infrastructure/repositories/applied_change_repository.py`
- `save_all(rows: list[AppliedSetpointChangeModel]) -> None` — `add_all` + `commit`.
- `latest_for_building(building_id: int) -> list[AppliedSetpointChangeModel]` — ordered `applied_at ASC, id ASC`.
- `exists_for_recommendation(recommendation_id: int) -> bool`
- `count_for_building(building_id: int) -> int`

**`DeviceRepository`** (extension in `backend/app/infrastructure/repositories/zone_repository.py` or a new sibling) — `first_hvac_for_zone(zone_id) -> DeviceModel | None`. Filter `lower(device_type) = 'hvac'` ordered by `id ASC`.

### Adapter
`DeviceControlAdapter` Protocol in `backend/app/infrastructure/adapters/device_control_adapter.py`:
```python
class DeviceControlAdapter(Protocol):
    def dispatch(
        self,
        device_id: int,
        zone_id: int,
        setpoint_delta_f: Decimal,
        run_timestamp: datetime,
        recommendation_id: int,
    ) -> DispatchOutcome: ...
```
Production stub raises `NotImplementedError`. Test double — `DeviceControlAdapterDouble` — colocated in the same module so the registry can flip to it on `use_test_doubles()`.

### API routes — `backend/app/api/routes/plans.py`
- `POST /api/buildings/{building_id}/plans/apply` body `{recommendation_ids: list[int]}` → 200 with `ApplyPlanRunResponse`, or 400 `{detail:{missingInputs:[...]}}` on `ApplyInputsMissing`, or 500 on DB error.
- `GET /api/buildings/{building_id}/plans/latest` → 200 with array of applied-change rows (oldest first).

### Wiring
Mount the new router in `backend/app/main.py`. When `TESTING=1`, also call `use_device_control_test_doubles()` to flip the registry.

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)
No change beyond extending the DB truncate (already covered in `database_reset.py`).

### Test doubles
**`DeviceControlAdapterDouble`** — `tests/acceptance/support/test_doubles/device_control_double.py`

Behavior:
- Default `dispatch(...)` returns `DispatchOutcome(status='dispatched', error_code=None, adapter_message='ok', latency_ms=5)` and appends `(recommendation_id, rank=None, zone_id, setpoint_delta_f)` to the call log.
- `set_directive(recommendation_id, outcome='dispatched'|'failed', error_code=None, adapter_message=None, latency_ms=None)` — programs the next dispatch for that rec_id.
- `force_db_error_next_apply()` — flips a flag so the next `dispatch` raises a sentinel `RuntimeError('forced_db_error_for_test')`; the route handler maps that to 500 (the service does NOT swallow it).
- `reset()` — clears directives, the call log, and the DB-error flag.

> Note: S15 is implemented as "next dispatch raises an exception that bubbles past the per-line catch" so the test exercises the route-level 500 path with `repo.save_all` never invoked. This is the cleanest way to assert atomicity without injecting SQL errors mid-commit.

The double is colocated at `backend/app/infrastructure/adapters/device_control_adapter.py` for in-process wiring; the harness reaches it via the test-only endpoint described below. (We follow the UC4 pattern of one source-of-truth class.)

### Test-only control endpoints (in `app/api/routes/test_support.py`)
- `POST /api/_test/device_control/directive` body `{recommendation_id, outcome, error_code?, adapter_message?, latency_ms?}` — programs a per-rec directive.
- `POST /api/_test/device_control/reset` — resets the double.
- `POST /api/_test/device_control/force_db_error` — sets the "next apply raises" flag.
- `POST /api/_test/devices/clear_for_zone` body `{zone_id, device_type?}` — deletes HVAC devices (default `device_type='hvac'`) for that zone, used by S12.

All mounted only when `TESTING=1`.

### Step definitions (`tests/acceptance/steps/UC5_steps.py`)
Reuses every UC3/UC4 step (building seeding, occupancy seeding, forecast doubles, comfort constraints, prior recommendation run). New UC5 steps:

| Step | Action |
|---|---|
| `Given the DeviceControlAdapter test double is reset` | POST `/api/_test/device_control/reset` |
| `Given the HVAC devices for zone "<zone>" of "<building>" are deleted` | POST `/api/_test/devices/clear_for_zone` |
| `Given the DeviceControlAdapter is configured to fail the rank N recommendation of "<building>" with error_code "<code>"` | Lookup rec id by rank via `/recommendations/latest`, POST directive |
| `Given the DeviceControlAdapter is configured to force a DB error on the next apply for "<building>"` | POST `/api/_test/device_control/force_db_error` |
| `Given the previous recommendation run for "<building>" is captured as the stale run` | GET `/recommendations/latest`, snapshot ids on `context.stale_run` |
| `Given a new successful recommendation run exists for "<building>" with N recommendation rows` | POST `/recommendations/run`; assert N |
| `When the FacilityManager applies the rank N recommendation for "<building>"` | Lookup ranked id, POST `/plans/apply` |
| `When the FacilityManager applies the rank R1, R2, ... recommendations for "<building>"` | Multi-rank id list |
| `When the FacilityManager applies all recommendations of the latest run for "<building>"` | GET `/recommendations/latest`, POST all ids |
| `When the FacilityManager applies the rank N recommendation for "<building>" again` | Second call; capture as `context.second_response` |
| `When the FacilityManager applies an unknown recommendation id for "<building>"` | POST with `{"recommendation_ids":[9999999]}` |
| `When the FacilityManager applies the rank N recommendation of "<otherBldg>" against building "<bldg>"` | Cross-building id |
| `When the FacilityManager applies the captured stale rank N recommendation for "<building>"` | Use `context.stale_run` ids |
| `When the FacilityManager applies the rank 1 recommendation for an unknown building id` | POST against id 9999999 |
| `When the user applies all recommendations of the latest run for "<building>" via the ApplyPlanPage` | Playwright drive |
| `Then the apply result contains N result rows` | assert 200 + len |
| `Then every apply result row has status "<s>"` | iterate results |
| `Then the apply result rows are ordered by rank ascending` | resolve ranks via `/recommendations/latest`, assert monotonic |
| `Then the DeviceControlAdapter was invoked N times for "<building>" in rank ascending order` | GET `/api/_test/device_control/calls` and assert |
| `Then the DeviceControlAdapter was invoked N times for "<building>"` | call count only |
| `Then the database contains N applied_setpoint_change rows for "<building>"` | GET `/plans/latest`, assert count |
| `Then each apply result row exposes recommendation_id, zone_id, setpoint_delta_f, status, error_code, adapter_message, and latency_ms` | field-presence check |
| `Then the apply is rejected with a missing-inputs error listing "<label>"` | reuse UC3/UC4 step (already present) |
| `Then the second apply result contains N result rows` | use `context.second_response` |
| `Then the second apply result row has status "<s>" with error_code "<code>"` | inspect first row of second response |
| `Then the apply result row for zone "<zone>" of "<building>" has status "<s>" with error_code "<code>"` | filter results by zone |
| `Then the apply result rows for zone "<zone>" of "<building>" all have status "<s>"` | filter results by zone, iterate |
| `Then the apply result row at rank R has status "<s>"` | resolve rank from `/recommendations/latest` and check |
| `Then the apply result row at rank R has status "<s>" with error_code "<code>"` | as above + error_code check |
| `Then the apply call fails with HTTP 500` | assert status 500 |
| `Then the apply call completes in under N milliseconds` | server `elapsed_ms` + client wall-clock |
| `Then the ApplyPlanPage displays N apply-result rows for "<building>"` | Playwright count `[data-testid^="apply-result-row-"]` |
| `Then the ApplyPlanPage shows the success banner` | `[data-testid="apply-success-banner"]` visible |
| `Then every ApplyPlanPage apply-status pill reads "<s>"` | iterate `[data-testid^="apply-status-"]` |

A read endpoint `GET /api/_test/device_control/calls` is added so the harness can inspect the double's call log without poking in-process state.

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC5-S01 Happy single | none beyond default | 1 `applied_setpoint_changes` row | `ApplyPlanService.apply`, `DeviceControlAdapterDouble` x1 |
| UC5-S02 Happy multi rank ASC | none | 3 rows | rank-ASC sort, adapter x3, call log ordered |
| UC5-S03 Approve all | none | 3 rows | bulk apply |
| UC5-S04 Single-zone boundary | none | 1 row | 1-zone path |
| UC5-S05 Multi-zone boundary | none | 5 rows | 5-zone path |
| UC5-S06 Field structure | none | row values | output schema |
| UC5-S07 Unknown building | none | 0 rows | service building check |
| UC5-S08 Unknown rec | none | 0 rows | service recommendation check |
| UC5-S09 Cross-building rec | none | 0 rows for A | service recommendation check |
| UC5-S10 Idempotency | none | 1 row | repo `exists_for_recommendation` short-circuit |
| UC5-S11 Stale run | none | 0 rows | service stale_run check |
| UC5-S12 Missing device | none | 3 rows (1 failed + 2 dispatched) | `DeviceRepository.first_hvac_for_zone` returns None |
| UC5-S13 Adapter failure | none | 3 rows (1 failed + 2 dispatched) | adapter directive |
| UC5-S14 Cross-building isolation | none | A=3, B=0 | transaction scope |
| UC5-S15 DB-error atomicity | none | 0 rows | route-level 500, rollback |
| UC5-S16 Performance | none | 10 rows | end-to-end timing |
| UC5-S17 UI execution summary | result rows, status pills, success banner | 3 rows | page lifecycle + adapter default |
