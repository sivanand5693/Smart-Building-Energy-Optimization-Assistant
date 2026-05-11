# Session Progress Log

## Current State
**Last Updated:** 2026-05-11 (UC1 scenario expansion + T4 cycles 2 and 3)
**Active Use Case:** UC1 RegisterBuildingProfile — expanded suite complete

## Status

### What's Done
- [x] UC1 RegisterBuildingProfile — T1→T4 complete, 17/17 scenarios pass (3 T4 cycles total; suite expanded 2026-05-11)
- [x] UC2 ImportOccupancySchedule — T1→T3 complete, 7/7 scenarios pass (no T4)
- [x] UC3 ForecastZoneDemand — T1→T3 complete, 7/7 scenarios pass on first run (no T4)
- [x] Project scaffolding (React + FastAPI + PostgreSQL + Behave + Playwright)
- [x] GitHub repo set up and pushed (UC1+UC2 commits)
- [x] Automation agent design document (`docs/automation_agent.md`)
- [x] Agent scaffolding (`AGENTS.md`, `init.sh`, `AGENT-PROGRESS.md`, `feature_list.json`, `feature_list.schema.json`, `.claude/agents/uc-pipeline-agent.md`)
- [x] Combined T1→T4 pipeline record format adopted (`docs/UCN/UCN_pipeline.md`) for UC3 onward

### What's In Progress
- [ ] None — UC3 is the most recent completed UC.

### What's Next
1. Commit the agent scaffolding + UC3 work (currently uncommitted; awaiting human approval).
2. UC4 RecommendHVACSetpointChanges — next use case in line.

## Blockers / Risks
- **Pending uncommitted work:** the working tree contains the `CLAUDE.md` edit from the prior session, all agent scaffolding, and the entire UC3 implementation. User has explicitly held commits until end-of-session.

## Decisions Made (this session)
- **Combined-markdown format**: each UC gets a `docs/UCN/UCN_pipeline.md` in addition to the existing 3-file T2 split. Preserves backward compatibility with UC1/UC2 while satisfying the assignment's single-file requirement.
  - Context: assignment says append T1→T4 outputs to one md file; project already has 3-file T2 convention from UC1/UC2.
  - Alternatives considered: switching all UCs to single-file format (rejected — would invalidate prior memory rule).
- **Agent runtime**: Claude Code sub-agent definition under `.claude/agents/uc-pipeline-agent.md`, executed inline by the main session. No standalone Python script.
- **UC3 trigger boundary (A4)**: HTTP endpoint `POST /api/buildings/{id}/forecasts/run`. Production scheduler integration deferred (out of scope for UC3).
- **UC3 adapters (A1–A3)**: All three external services wrapped behind Protocol interfaces with deterministic in-memory doubles. Real impls stubbed as `NotImplementedError`. Real scikit-learn / weather-API integration deferred.
- **Test-only control endpoints under `/api/_test/...`**: New pattern (not used in UC1/UC2). Mounted only when `TESTING=1` so they cannot leak to prod. Lets step defs seed/clear adapter state via HTTP, matching the UC1/UC2 over-HTTP harness style.
- **Atomicity via single transaction**: `ForecastService.run_forecast` checks all four input categories before any DB write; raises `ForecastInputsMissing` on any miss. `commit()` only happens after model predictions are appended.

## Files Modified This Session

**Scaffolding:**
- `docs/automation_agent.md` — new design document (~280 lines)
- `AGENTS.md` — new
- `init.sh` — new (executable)
- `AGENT-PROGRESS.md` — this file
- `feature_list.json` — new (UC1+UC2 marked pass; UC3 flipped to pass at finalization)
- `feature_list.schema.json` — new
- `.claude/agents/uc-pipeline-agent.md` — sub-agent definition

**UC3 docs:**
- `docs/UC3/structured_requirement.md` — new
- `docs/UC3/ui_design.md` — new
- `docs/UC3/db_design.md` — new
- `docs/UC3/harness_design.md` — new
- `docs/UC3/UC3_pipeline.md` — new (combined T1→T4 record)
- `docs/UC3/acceptance_status.md` — new

**UC3 code:**
- `tests/acceptance/features/UC3_ForecastZoneDemand.feature` — new
- `tests/acceptance/steps/UC3_steps.py` — new
- `tests/acceptance/support/database_reset.py` — added `demand_forecasts` to truncate
- `backend/app/domain/forecast.py` — new
- `backend/app/infrastructure/models/forecast_model.py` — new
- `backend/app/infrastructure/models/__init__.py` — export `DemandForecastModel`
- `backend/app/infrastructure/repositories/forecast_repository.py` — new
- `backend/app/infrastructure/repositories/occupancy_repository.py` — added `latest_for_zone`
- `backend/app/infrastructure/adapters/forecast_adapters.py` — new (Protocols + doubles + registry)
- `backend/app/services/forecasting_service.py` — new
- `backend/app/api/routes/forecasting.py` — new
- `backend/app/api/routes/test_support.py` — new (TESTING-only)
- `backend/app/main.py` — wire forecasting + test_support routers; switch to doubles when `TESTING=1`
- `backend/alembic/versions/1a325eb44672_uc3_demand_forecasts.py` — new migration

**Frontend:**
- `frontend/src/pages/ForecastPage/index.tsx` — new
- `frontend/src/types/index.ts` — added `ZoneForecast`, `ForecastRunResponse`
- `frontend/src/services/api.ts` — added `runForecast`, `getLatestForecasts`
- `frontend/src/App.tsx` — added `/forecasts` route

**Loose end (from prior session):**
- `CLAUDE.md` — added `docs/UCN/acceptance_status.md` tracking rule (uncommitted since prior session)

## Evidence of Completion
- [x] UC3 acceptance tests: 7/7 scenarios pass, 69 steps, 0.71s — `PYTHONPATH="./backend:." behave tests/acceptance/features/UC3_ForecastZoneDemand.feature`
- [x] Full regression UC1+UC2+UC3: 19/19 scenarios pass, 181 steps, 3.04s
- [x] Frontend type check + build clean: `npm run build` (38 modules transformed)
- [x] Both DBs (`smart_building_dev`, `smart_building_test`) on revision `1a325eb44672`

## Notes for Next Session
UC3 is fully done. UC4 is next: RecommendHVACSetpointChanges, FacilityManager-triggered, depends on UC3 forecasts. The forecasting adapter pattern set up in UC3 will likely extend to UC4's optimization adapter.

---

## UC1 Expansion Session — 2026-05-11

### Scope
Extended UC1 acceptance suite from 5 to 17 scenarios (S06–S17 added). Two new T4 cycles required.

### Decisions
- **S10 — Duplicate zone-name validation (Option 1 chosen):** added a duplicate-name check inside `BuildingService._validate` rather than at the repository or DB layer. Keeps validation co-located with the other field checks and reuses the same `errors["zones"]` shape/path. Message wording made to include the literal `zones` substring so the harness assertion (`field in text_content`) passes.
- **S14 — Drop unique constraint on `buildings.name` (Option 1 chosen):** the structured requirement does not mandate building-name uniqueness. Removed `unique=True` from `BuildingModel.name` and shipped a new Alembic migration (`b4e9c1a07f23`) chained off the UC3 head `1a325eb44672`. Applied to both `smart_building_dev` and `smart_building_test`.

### Files Modified
- `backend/app/services/building_service.py` — added duplicate zone-name pre-check inside `_validate` (wording revised once to satisfy harness assertion).
- `backend/app/infrastructure/models/building_model.py` — dropped `unique=True` from `name`.
- `backend/alembic/versions/b4e9c1a07f23_uc1_drop_building_name_unique.py` — new migration (drop_constraint `buildings_name_key`).
- `docs/UC1/acceptance_status.md` — rewritten for 17/17, 3 T4 cycles, regression notes.
- `docs/UC1/failure_bundles/UC1-S10_duplicate_zone_names.md` — bundle exists from prior turn.
- `docs/UC1/failure_bundles/UC1-S14_unique_building_name_constraint.md` — bundle exists from prior turn.
- `feature_list.json` — UC1 evidence updated (17/17, 3 T4 cycles, testedAt 2026-05-11); UC3 evidence regression line updated to 31/31.
- `AGENT-PROGRESS.md` — this entry.

### No `UC1_pipeline.md`
UC1 predates the combined-markdown convention (introduced for UC3). The expansion session does not retro-create one; the per-file artifacts plus this AGENT-PROGRESS entry serve as the trail.

### Evidence
- UC1 scenario suite: **17 / 17 pass**, 173 steps, 3.85s.
- Full regression UC1+UC2+UC3: **31 / 31 pass**, 307 steps, 5.72s.
- Both DBs migrated to head `b4e9c1a07f23`.

---

## UC2 Expansion Session — 2026-05-11

### Scope
Extended UC2 acceptance suite from 7 to 16 scenarios. Added 9 new scenarios (S08–S16) exercising cross-building zone isolation, negative-count handling, non-integer `zone_id`, wrong column count, multi-row error aggregation, blank-line tolerance, header-whitespace tolerance (documents current behavior — no code change needed), submit-button gating, and header-only file rejection. No T4 cycles required — all 9 new scenarios passed on the first acceptance run.

### Decisions
- **No production code changes.** Every new scenario aligns with existing `BuildingService.import_occupancy_schedule` behavior. S14 (header whitespace) and S15 (submit gating) explicitly serve as regression locks documenting current behavior.
- **S08 (cross-building zone) seeding pattern:** introduced a new given step `a second building "X" exists with zone "Y"` that seeds independent buildings, storing them on `context.other_buildings` so the harness can craft a CSV referencing a zone owned by a different building.
- **Templated raw CSV pattern (S13/S14):** added `step_upload_raw_templated` which substitutes `{ZoneName}` tokens in raw CSV blocks with the seeded zone_id, so docstring CSVs in the feature file can reference zones by name without leaking auto-generated IDs into Gherkin.

### Files Modified
- `tests/acceptance/features/UC2_ImportOccupancySchedule.feature` — appended S08–S16 (9 scenarios).
- `tests/acceptance/steps/UC2_steps.py` — added 3 new step defs (`a second building exists with zone`, `an import error references row N without naming a field`, `the submit button is disabled`), 2 helper steps (cross-building row, templated raw CSV), and `an import error indicates no data rows`. Imported `re` for token substitution.
- `docs/UC2/structured_requirement.md` — appended 9 rows to §B Acceptance Checks Table and 9 oracles to §C Acceptance Oracles.
- `docs/UC2/acceptance_status.md` — rewritten for 16/16, 0 T4 cycles, expanded scenario table.
- `feature_list.json` — UC2 evidence updated (16/16, testedAt 2026-05-11). UC1 and UC3 evidence lines refreshed to reflect 40/40 regression.
- `AGENT-PROGRESS.md` — this entry.

### Pre-flight gotcha
The initial run failed all 16 scenarios at `wait_for_function` for the building dropdown. Root cause: a dev backend (PIDs 12279/12281) was already bound to port 8000, so Behave's `_start_backend` health-checked the wrong process — Vite proxied `/api` to the dev DB (which had no rows). Killing the dev backend resolved the conflict immediately; no harness code change required.

### No `UC2_pipeline.md`
UC2 predates the combined-markdown convention (introduced for UC3). The expansion session does not retro-create one; per-file artifacts plus this AGENT-PROGRESS entry serve as the trail.

### Evidence
- UC2 scenario suite: **16 / 16 pass**, 145 steps, 2.79s.
- Full regression UC1+UC2+UC3: **40 / 40 pass**, 387 steps, 7.31s.
