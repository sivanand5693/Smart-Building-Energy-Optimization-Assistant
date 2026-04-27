# Session Progress Log

## Current State
**Last Updated:** 2026-04-27 (UC3 finalization)
**Active Use Case:** UC3 ForecastZoneDemand — complete

## Status

### What's Done
- [x] UC1 RegisterBuildingProfile — T1→T4 complete, 5/5 scenarios pass (1 T4 cycle)
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
