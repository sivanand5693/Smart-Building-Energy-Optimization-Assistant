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
PYTHONPATH="./backend" pytest tests/unit/
PYTHONPATH="./backend" pytest tests/unit/test_building_service.py  # single file
```

### Frontend
```bash
cd frontend && npm run dev          # Vite dev server on :5173
```

### Database
```bash
createdb smart_building_dev
createdb smart_building_test
cd backend
alembic upgrade head                 # dev DB
TESTING=1 alembic upgrade head       # test DB
```

### Acceptance Tests
Behave auto-starts the backend in `TESTING=1` mode on port 8000 against `smart_building_test`. Vite must be running in another terminal for UI scenarios.
```bash
PYTHONPATH="./backend:." behave tests/acceptance/features/
PYTHONPATH="./backend:." behave tests/acceptance/features/UC1_RegisterBuildingProfile.feature  # single UC
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
- Each UC tracks its test status in `docs/UCN/acceptance_status.md` — update after every acceptance run
