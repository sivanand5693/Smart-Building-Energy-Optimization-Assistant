# UC5 ApplyApprovedEnergyPlan — T1→T4 Combined Pipeline Record

- **UC ID:** UC5
- **UC Name:** ApplyApprovedEnergyPlan
- **Date:** 2026-06-01
- **Pipeline:** T1 → T2 → T3 (→ T4 if needed)
- **Methodology:** `ref/Acceptance Testing Methodology for AI-Generated Code with UI and DB Integration.pdf` (T1 pp. 15–16; T2 p. 19; T3 p. 22; T4 p. 25)

---

## T1 — Use Case → Structured Requirement + Gherkin

### Part A) Structured Requirement
See `docs/UC5/structured_requirement.md` §A. Trigger boundary `POST /api/buildings/{id}/plans/apply`; per-line apply outcomes persisted in new `applied_setpoint_changes` table; idempotency via `recommendation_id` UNIQUE + service short-circuit; latest-run-only enforcement.

### Part B) Gherkin Suite
17 scenarios in `tests/acceptance/features/UC5_ApplyApprovedEnergyPlan.feature` (S01–S17), covering happy single/multi/all, boundaries, field-structure, validation failures (building/recommendation/stale_run), idempotency, missing device, adapter failure, cross-building isolation, DB-error atomicity, performance, and UI execution summary.

Coverage table in `structured_requirement.md` §B; oracles in §C; nine numbered assumptions in §D.

---

## T2 — Gherkin → UI + DB + Harness Design

- **Part A — UI design:** `docs/UC5/ui_design.md` — `ApplyPlanPage` at `/apply-plan`; testids `apply-run-button`, `apply-result-row-N`, `apply-status-N`, `apply-error-N`, `apply-success-banner`, `apply-error-banner`, `apply-missing-inputs`, `apply-building-selector`, plus per-recommendation approval checkboxes.
- **Part B — DB design:** `docs/UC5/db_design.md` — new `applied_setpoint_changes` table chained off UC4 head `a91c2f3d7e84`; truncate rule extended; UNIQUE on `recommendation_id`, CHECK on `status`.
- **Parts C/D/E — Service & harness:** `docs/UC5/harness_design.md` — `ApplyPlanService` (atomic single-transaction batch), `AppliedChangeRepository`, `DeviceControlAdapter` Protocol + deterministic double, four new `/api/_test/...` endpoints (`device_control/directive`, `device_control/reset`, `device_control/force_db_error`, `devices/clear_for_zone`), plus `/api/_test/device_control/calls` read endpoint for the call log. Traceability table maps every scenario to UI/DB/service surface.

---

## T3 — Contract + Design → Implementation

### Code shipped
- `backend/alembic/versions/c7d2a1f9e5b0_uc5_applied_setpoint_changes.py` — migration chained off `a91c2f3d7e84`; creates `applied_setpoint_changes` with UNIQUE(`recommendation_id`), CHECK on `status`, FKs to building/zone/recommendation, `(building_id, applied_at)` index.
- `backend/app/domain/applied_change.py` — `DispatchOutcome`, `AppliedChange`, `ApplyPlanRunResult`, `ApplyInputsMissing`, `ApplyForcedDbError`.
- `backend/app/infrastructure/models/applied_setpoint_change_model.py` + `__init__.py` export.
- `backend/app/infrastructure/repositories/applied_change_repository.py` — `AppliedChangeRepository` and `DeviceRepository.first_hvac_for_zone` / `delete_hvac_for_zone` (case-insensitive `lower(device_type)='hvac'`).
- `backend/app/infrastructure/adapters/device_control_adapter.py` — Protocol + production stub + `DeviceControlAdapterDouble` (directive map, call log, force-DB-error flag).
- `backend/app/services/apply_plan_service.py` — building load, latest-run resolution, recommendation ownership + staleness validation, rank-ASC dispatch loop, per-line `missing_device` / `already_applied` short-circuits, single-transaction `save_all`.
- `backend/app/api/routes/plans.py` — `POST /api/buildings/{id}/plans/apply` (400 on `ApplyInputsMissing`, 500 on `ApplyForcedDbError` with explicit rollback), `GET /api/buildings/{id}/plans/latest`.
- `backend/app/api/routes/test_support.py` — added `device_control/{directive,reset,force_db_error,calls}` and `devices/clear_for_zone`.
- `backend/app/main.py` — wired `plans.router` and `use_device_control_test_doubles()` under `TESTING=1`.
- `backend/app/api/routes/recommendations.py` + `backend/app/services/recommendation_service.py` + `backend/app/domain/recommendation.py` — propagated `id` to API output so the UI and step defs can select recommendations by id (rank-resolution helper).
- `tests/acceptance/support/database_reset.py` — TRUNCATE list now leads with `applied_setpoint_changes`.
- `tests/acceptance/steps/UC5_steps.py` — full step library; reuses UC1/UC3/UC4 background steps.
- Frontend: `frontend/src/pages/ApplyPlanPage/index.tsx` (testids `apply-building-selector`, `latest-run-row-*`, `apply-approve-*`, `apply-run-button`, `apply-result-table`, `apply-result-row-N`, `apply-status-N`, `apply-error-N`, `apply-success-banner`, `apply-error-banner`, `apply-missing-inputs`), `frontend/src/App.tsx` (+`/apply-plan` route), `frontend/src/services/api.ts` (`applyPlan`, `getLatestPlan`), `frontend/src/types/index.ts` (`AppliedChange`, `ApplyPlanResponse`, `SetpointRecommendation.id`).
- `CLAUDE.md` — Per-UC routes block now lists UC5 `/apply-plan`.

### Notes
- During the first acceptance run, scenario S13 surfaced a behave/parse ordering quirk: the shorter step `the apply result row at rank {rank:d} has status "{status}"` had been registered before its longer sibling `... has status "{status}" with error_code "{code}"`, so behave greedily matched the shorter pattern and crammed the trailing `with error_code "adapter_error"` into the `status` field. Resolution: reorder the two step decorators in `UC5_steps.py` so the more specific step is registered first. This is a step-definitions-only fix; the feature file was not modified.

### Evidence
- `PYTHONPATH="./backend:." behave tests/acceptance/features/UC5_ApplyApprovedEnergyPlan.feature` → **17 / 17 pass**, 291 steps, 3.24s.
- Full regression `UC1+UC2+UC3+UC4+UC5` → **84 / 84 pass**, 1019 steps, 14.28s.
- Both `smart_building_dev` and `smart_building_test` on revision `c7d2a1f9e5b0`.

---

## T4 — Failure Bundle → Minimal Patch

Not required. No `.feature`-driven failure cycle occurred. The S13 step-decorator reorder is captured in the T3 notes above; no failure bundle written.

