# UC6 AdaptPlanToOccupancyChange — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`AdaptPlanService`** — `backend/app/services/adapt_plan_service.py`

Module constant:
```python
MATERIAL_OCCUPANCY_DELTA_FRACTION = Decimal("0.30")
```

Public methods:
- `adapt(building_id: int, occupancy_changes: list[OccupancyChange]) -> AdaptPlanResult`
- `list_for_building(building_id: int) -> list[AdaptDecision]`

`adapt` steps (all inside one `db` session, single commit at the end):
1. Load `BuildingModel` by id. Missing → raise `AdaptInputsMissing(["building"])`.
2. Validate `occupancy_changes` length > 0. Empty → raise `AdaptInputsMissing(["occupancy_changes"])`.
3. Build the zone-id set from `building.zones`. Any `change.zone_id` outside that set → raise `AdaptInputsMissing(["zone"])`.
4. Resolve **active plan**: latest `setpoint_recommendations.run_timestamp` for the building whose ids intersect ≥1 `applied_setpoint_changes` row (any status). None → raise `AdaptInputsMissing(["active_plan"])`.
5. For each change in the payload:
   - Insert `OccupancyRecordModel(zone_id, timestamp=now(), occupancy_count=new)` (session-level, not committed yet).
   - Load baseline via `occupancy_repo.latest_for_zone_at_or_before(zone_id, active_plan_run_timestamp)`. None → baseline = 0.
   - Compute `delta_fraction = abs(new - baseline) / max(baseline, 1)`.
   - If `delta_fraction >= MATERIAL_OCCUPANCY_DELTA_FRACTION`, append `zone_id` to `changed_zone_ids` (ordered by payload position for deterministic test assertions).
6. If `changed_zone_ids` is non-empty:
   - `inner = RecommendationService(db).run_within(building_id, db=db, commit=False)` → returns a `RecommendationRunResult` whose rows were flushed but not committed.
   - `decision = 'replanned'`, `reason = 'material occupancy delta'`, `new_run_timestamp = inner.run_timestamp`.
   - `logging.getLogger(__name__).info("plan_adapt_replan", extra={...})`.
   Else:
   - `decision = 'no_replan'`, `reason = 'no material change'`, `new_run_timestamp = None`, `revised_recommendations = []`.
7. Insert one `PlanAdaptationEventModel` row.
8. `db.commit()`.
9. Return `AdaptPlanResult(building_id, decision, reason, active_plan_run_timestamp, new_run_timestamp, changed_zone_ids, revised_recommendations, elapsed_ms)`.

Atomicity: any exception inside the try block → `db.rollback()` + re-raise (route maps `AdaptInputsMissing` → 400, everything else → 500).

### Domain types — `backend/app/domain/plan_adaptation.py`
- `OccupancyChange(zone_id: int, new_occupancy_count: int)` — input dataclass.
- `AdaptDecision(building_id, decision, reason, active_plan_run_timestamp, new_run_timestamp, changed_zone_ids, requested_at, elapsed_ms)` — event-row view.
- `AdaptPlanResult(...)` — adds `revised_recommendations: list[RankedRecommendation]`.
- `AdaptInputsMissing(Exception)` with `missing_inputs: list[str]`.

### Repositories
**`PlanAdaptationRepository`** — new, `backend/app/infrastructure/repositories/plan_adaptation_repository.py`
- `save(model: PlanAdaptationEventModel) -> None` — `add` only (commit is owned by the service).
- `latest_for_building(building_id) -> PlanAdaptationEventModel | None`
- `list_for_building(building_id) -> list[PlanAdaptationEventModel]` — ordered `requested_at DESC, id DESC`.
- `count_for_building(building_id) -> int`

**`SetpointRecommendationRepository`** (extended)
- `active_plan_run_timestamp(building_id) -> datetime | None` — latest `run_timestamp` whose ids intersect ≥1 `applied_setpoint_changes` row.

**`OccupancyRepository`** (extended)
- `latest_for_zone_at_or_before(zone_id, ts) -> OccupancyRecordModel | None`
- `add(record: OccupancyRecordModel) -> None` — adds without commit (so the outer transaction owns commit).

### RecommendationService addition
- New method `run_within(building_id: int, *, db: Session, commit: bool = False) -> RecommendationRunResult`. Mirrors `run` but flushes (`db.flush()`) instead of committing when `commit=False`. The existing `run(building_id)` is rewritten as a thin wrapper that calls `run_within(building_id, db=self.db, commit=True)`.
- `SetpointRecommendationRepository.save_all_no_commit(rows)` — used by `run_within` when `commit=False`.

### Adapter
No new adapter. Reuses `OptimizationAdapter` via `RecommendationService.run_within`.

### API routes — `backend/app/api/routes/plans.py`
- `POST /api/buildings/{building_id}/plan/adapt` body `{occupancy_changes: [{zone_id, new_occupancy_count}, ...]}` → 200 `AdaptPlanResponse`, 400 `{detail:{missingInputs:[...]}}`, 500.
- `GET /api/buildings/{building_id}/plan/adaptations` → 200 list of `AdaptDecisionOut` ordered by `requested_at DESC`.

### Wiring
Same `plans.py` router (already mounted in `main.py`). No new module to register.

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)
No change beyond extending the DB truncate (covered in `database_reset.py`).

### Test doubles
No new doubles — UC6 reuses the existing `OptimizationAdapterDouble` (UC4), `ForecastModelDouble` / `WeatherAdapterDouble` / `DeviceStateAdapterDouble` (UC3), and `DeviceControlAdapterDouble` (UC5).

### Test-only control endpoints (added to `app/api/routes/test_support.py`)
- `POST /api/_test/occupancy/set_for_zone` body `{zone_id, occupancy_count, timestamp?}` — clears existing rows for that zone and inserts one row with the given count (and optional timestamp). Used by S08 ("set baseline to 100") and S05/S06 ("force baseline=100 for crisp 29 / 30 % math").

### Step definitions (`tests/acceptance/steps/UC6_steps.py`)
Reuses every UC3/UC4/UC5 step (background seeding, recommendation runs, apply). New UC6 steps:

| Step | Action |
|---|---|
| `Given the FacilityManager has applied the rank N recommendation for "<bldg>"` | Given-form alias of UC5's apply step; uses `_rec_id_for_rank` + `POST /plans/apply` |
| `Given the latest occupancy snapshot for zone "<zone>" of "<bldg>" is set to N` | POST `/api/_test/occupancy/set_for_zone` with explicit count and ts < active plan |
| `When the OccupancyDataService reports occupancy changes for "<bldg>":` (table) | POST `/plan/adapt` with translated zone ids |
| `When the OccupancyDataService reports the same occupancy changes for "<bldg>" again` | Replay last payload, store as `context.second_response` |
| `When the OccupancyDataService reports a N percent jump for zone "<zone>" of "<bldg>"` | Set baseline=100 via test endpoint, then POST adapt with `new=100*(1+N/100)` |
| `When the OccupancyDataService reports an occupancy change against an unknown building id` | POST `/api/buildings/9999999/plan/adapt` |
| `When the OccupancyDataService reports occupancy changes for "<bldg>" referencing an unknown zone` | POST `/plan/adapt` with `zone_id=9999999` |
| `When the OccupancyDataService reports an empty occupancy_changes payload for "<bldg>"` | POST with `{"occupancy_changes": []}` |
| `When the user submits an occupancy change for zone "<zone>" of "<bldg>" with count N via the AdaptPlanPage` | Playwright drive `/adapt-plan` |
| `Then the adapt response has decision "<d>"` | assert 200 + body.decision |
| `Then the second adapt response has decision "<d>"` | use `context.second_response` |
| `Then the adapt response changed_zone_ids list zones [...] for "<bldg>"` | translate zone names → ids, set-equal compare with `body.changed_zone_ids` |
| `Then the adapt response includes a non-null new_run_timestamp` | field check |
| `Then the adapt response new_run_timestamp is null` | field check |
| `Then the database contains N plan_adaptation_events rows for "<bldg>"` | GET `/plan/adaptations`, assert count |
| `Then a new setpoint_recommendations run was created for "<bldg>"` | snapshot count before adapt in helper; assert count after > before |
| `Then no new setpoint_recommendations run was created for "<bldg>"` | snapshot vs after; equal |
| `Then the adapt is rejected with a missing-inputs error listing "<label>"` | reuse UC5 step (already covers `the adapt is rejected` via the shared assertion helper; we add a UC6-specific alias) |
| `Then the adapt call completes in under N milliseconds` | server `elapsed_ms` + client wall-clock |
| `Then the AdaptPlanPage shows the success banner` | Playwright |
| `Then the AdaptPlanPage decision pill reads "<d>"` | Playwright |
| `Then the AdaptPlanPage reason text is non-empty` | Playwright |
| `Then the AdaptPlanPage lists zone "<zone>" of "<bldg>" as a changed zone` | Playwright `adapt-changed-zone-{id}` |
| `Then the AdaptPlanPage revised-recs table displays N rows` | Playwright count `[data-testid^="adapt-revised-rec-row-"]` |

A helper `_snapshot_rec_count(context, building_name)` records the current `setpoint_recommendations` row count before the adapt action; the "new run was/was not created" assertions diff against that snapshot.

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC6-S01 Happy single-zone replan | none beyond default | 1 adapt event, 1 occupancy row, 1 new rec run | `AdaptPlanService.adapt` → `RecommendationService.run_within` |
| UC6-S02 Happy multi-zone replan | none | 1 adapt event, 3 occupancy rows, 1 new rec run | materiality on 2 of 3 |
| UC6-S03 Mixed material + non-material | none | 1 adapt event, 3 occupancy rows, 1 new rec run, changed=[Lobby] | filter test |
| UC6-S04 No-replan path | none | 1 adapt event, 3 occupancy rows, no new rec run | short-circuit |
| UC6-S05 Threshold below 29% | none | 1 adapt event (no_replan) | `set_for_zone(100)` then submit 129 |
| UC6-S06 Threshold at 30% | none | 1 adapt event (replanned) | submit 130 |
| UC6-S07 Zero-baseline | none | 1 adapt event (replanned) | baseline=0 branch |
| UC6-S08 Negative drop 100→60 | none | 1 adapt event (replanned) | abs() branch |
| UC6-S09 No active plan | none | 0 adapt events | active-plan check |
| UC6-S10 Unknown building | none | 0 adapt events | building check |
| UC6-S11 Unknown zone | none | 0 adapt events, 0 occupancy rows | zone check, atomicity |
| UC6-S12 Empty payload | none | 0 adapt events | length check |
| UC6-S13 Mixed UC5 applied state | none | 1 adapt event, 1 new rec run | active-plan resolver tolerates `failed` rows |
| UC6-S14 Determinism on repeat | none | 2 adapt events, only first replans | baseline updates between calls |
| UC6-S15 Cross-building isolation | none | A=1 event, B=0 events, B no new rec run | building scoping |
| UC6-S16 Performance | none | 1 adapt event, 1 new 5-row rec run | <2000 ms budget |
| UC6-S17 UI flow | banner, decision pill, reason, changed-zone chip, revised-recs table | 1 adapt event, 1 new rec run | `/adapt-plan` page |
