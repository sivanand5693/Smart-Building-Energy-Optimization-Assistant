# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> See **README.md** for project overview, use cases, tech stack, and setup instructions.
> See `ref/` for source documents (use case specs and methodology PDF).

## Development Methodology

Follow the 4-template prompt pipeline for every use case — do not skip steps:

1. **T1** — Use Case → Structured Requirement + Gherkin
2. **T2** — Gherkin → UI + DB + Acceptance Harness Design
3. **T3** — Contract + Design → Implementation
4. **T4** — Failure Bundle → Minimal Patch (only when tests fail)

Implement and validate **one use case at a time**. Save artifacts to `docs/UCN/`.

## Commands

### Backend
```bash
source .venv/bin/activate
cd backend && uvicorn app.main:app --reload
pytest tests/unit/
pytest tests/unit/test_building_service.py  # single file
```

### Frontend
```bash
cd frontend && npm start
```

### Database
```bash
createdb smart_building_dev
cd backend && alembic upgrade head
```

### Acceptance Tests
```bash
behave tests/acceptance/features/
behave tests/acceptance/features/UC1_RegisterBuildingProfile.feature  # single UC
```

## Architecture

```
React UI → FastAPI routes → Services → Repositories → PostgreSQL
```

- `api/routes/` — route handlers only, no business logic
- `services/` — all business logic, one file per use case group
- `domain/` — pure Python entities, no DB dependencies
- `infrastructure/repositories/` — all SQL, services never write queries directly
- `infrastructure/adapters/` — wrappers for forecasting, device control, Claude API

### Key Rules
- React pages must be thin — inputs, API calls, rendered outputs only
- Never change a `.feature` file to make a test pass — fix the implementation
- Always use test doubles in `tests/acceptance/support/test_doubles/` during acceptance runs, never real adapters
- Repositories own all SQL — services call repositories only
