# UC4 RecommendHVACSetpointChanges — Pipeline Log

| Field | Value |
|---|---|
| UC ID | UC4 |
| Name | RecommendHVACSetpointChanges |
| Started | 2026-06-01 |
| Status | pass |

## T1 — Structured Requirement + Gherkin

Outputs:
- `docs/UC4/structured_requirement.md` (Part A structured requirement, Part B acceptance checks table, Part C oracles, Part D assumptions A1-A7).
- `tests/acceptance/features/UC4_RecommendHVACSetpointChanges.feature` (17 scenarios UC4-S01..S17).

Summary: Trigger boundary is `POST /api/buildings/{id}/recommendations/run`. Service loads building+zones, latest demand forecast per zone (fail if any missing or older than 24h), per-zone comfort constraints (fail if missing), calls `OptimizationAdapter.recommend` per zone, filters infeasible candidates (`new_setpoint` outside `[min,max]`), ranks survivors by `projected_savings_kwh DESC` with tie-breaker `(zone_id ASC, setpoint_delta_f ASC)`, persists one `setpoint_recommendations` row per surviving candidate in one transaction. `GET /api/buildings/{id}/recommendations/latest` returns rows of the most recent run ordered by `rank ASC`. Assumptions A1-A7 cover comfort-store schema (no editor UI), 24h staleness rule, adapter Protocol + deterministic double, HTTP trigger boundary, closed `comfort_impact` enum, UC5 deferral, and tie-breaker.

## T2 — UI + DB + Harness Designs

Outputs:
- `docs/UC4/ui_design.md` (Part A): RecommendationsPage at `/recommendations` with selector + run button; success / error panels; rows keyed by rank.
- `docs/UC4/db_design.md` (Part B): new `zone_comfort_constraints` (PK zone_id) and `setpoint_recommendations` (id PK, building_id+zone_id FKs, run_timestamp, delta, savings, impact enum, rank, model_version) tables; indexes on `(building_id, run_timestamp DESC)` and `(building_id, run_timestamp, rank)`. Reset truncate list extended.
- `docs/UC4/harness_design.md` (Parts C, D, E): `RecommendationService` flow, `OptimizationAdapter` Protocol + double, repositories, route, test-only seed/clear endpoints, step-def list, traceability table.

## T3 — Implementation

Backend:
- `backend/app/domain/recommendation.py` (Candidate, RankedRecommendation, RecommendationRunResult, RecommendationInputsMissing)
- `backend/app/infrastructure/models/zone_comfort_constraint_model.py`
- `backend/app/infrastructure/models/setpoint_recommendation_model.py`
- `backend/app/infrastructure/models/__init__.py` (registered both new models)
- `backend/app/infrastructure/adapters/optimization_adapter.py` (Protocol, production stub, `OptimizationAdapterDouble`, registry, `use_test_doubles`)
- `backend/app/infrastructure/repositories/recommendation_repository.py` (`SetpointRecommendationRepository`, `ZoneComfortConstraintRepository`)
- `backend/app/infrastructure/repositories/forecast_repository.py` (added `latest_for_zone`)
- `backend/app/services/recommendation_service.py` (`RecommendationService.run` + `latest_for_building`; 24h staleness check, midpoint baseline feasibility filter, ranked persistence, atomic transaction)
- `backend/app/api/routes/recommendations.py` (`POST /api/buildings/{id}/recommendations/run`, `GET .../latest`)
- `backend/app/api/routes/test_support.py` (added comfort_constraints seed/clear, forecasts force_stale/clear_for_zone, optimization_double force_infeasible/reset)
- `backend/app/main.py` (router + `use_optimization_test_doubles`)
- `backend/alembic/versions/a91c2f3d7e84_uc4_recommendations.py` (down_revision `b4e9c1a07f23`)

Frontend:
- `frontend/src/pages/RecommendationsPage/index.tsx` (selector + run button + table; testids `recommendation-row-{rank}`, `recommendation-run-error`, `recommendation-missing-inputs`, `recommendation-run-button`, `recommendation-run-success`, `recommendation-building-selector`, `recommendation-table`)
- `frontend/src/services/api.ts` (`runRecommendations`, `getLatestRecommendations`)
- `frontend/src/types/index.ts` (`SetpointRecommendation`, `RecommendationRunResponse`)
- `frontend/src/App.tsx` (route `/recommendations`)

Tests / harness:
- `tests/acceptance/features/UC4_RecommendHVACSetpointChanges.feature` (17 scenarios)
- `tests/acceptance/steps/UC4_steps.py` (reuses UC3 building/occupancy/forecast steps + 400-error step)
- `tests/acceptance/support/test_doubles/optimization_adapter_double.py` (re-exports the in-process double)
- `tests/acceptance/support/database_reset.py` (extended truncate list)

Docs / config:
- `CLAUDE.md` — added Per-UC browser route for UC4.

## T4 — Failure Bundle -> Minimal Patch

Not needed. UC4 suite passed 17/17 on first behave run.

## Finalization

- UC4 suite: 17/17 scenarios, 230/230 steps, 2.85s.
- Regression (UC1+UC2+UC3+UC4): 67/67 scenarios, 728/728 steps, 11.19s.
- `feature_list.json` updated: UC4 status `pass`.
- `docs/UC4/acceptance_status.md` written.
