# Smart Building Energy Optimization Assistant

CISC 699 — Applied Project | Harrisburg University | Late Spring 2026
**Author:** Sivanand Puliyadi Ravi

---

## Overview

The Smart Building Energy Optimization Assistant is a web application that helps facility managers optimize energy usage across building zones. It forecasts zone-level energy demand, recommends HVAC setpoint changes, applies approved energy plans, monitors comfort risk, and generates daily savings reports — all with AI-assisted explanations and graceful handling of sensor outages.

---

## Use Cases

| # | Use Case | Primary Actor |
|---|---|---|
| UC1 | RegisterBuildingProfile | FacilityManager |
| UC2 | ImportOccupancySchedule | FacilityManager |
| UC3 | ForecastZoneDemand | Scheduler |
| UC4 | RecommendHVACSetpointChanges | FacilityManager |
| UC5 | ApplyApprovedEnergyPlan | FacilityManager |
| UC6 | AdaptPlanToOccupancyChange | OccupancyDataService |
| UC7 | DetectComfortViolationRisk | Scheduler |
| UC8 | ExplainRecommendation | FacilityManager |
| UC9 | GenerateDailySavingsReport | FacilityManager |
| UC10 | HandleSensorDataOutage | MonitoringService |

Full use case specifications are in `ref/Project4_UseCases.docx`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Tailwind CSS |
| Backend | Python + FastAPI + SQLAlchemy |
| Database | PostgreSQL |
| Forecasting | scikit-learn |
| Optimization | Rule-based engine |
| Explanations | Anthropic Claude API |
| Acceptance Testing | Behave + Playwright |
| Unit Testing | Pytest |

---

## Development Methodology

This project follows an **acceptance-testing methodology for AI-generated code** using a 4-template prompt pipeline:

- **T1** — Use Case → Structured Requirement + Gherkin
- **T2** — Gherkin → Integrated UI + DB + Acceptance Harness Design
- **T3** — Contract + Design → Integrated Implementation
- **T4** — Failure Bundle → Minimal Patch

Each use case is implemented and validated separately before moving to the next. Full methodology is in `ref/Acceptance Testing Methodology for AI-Generated Code with UI and DB Integration.pdf`.

---

## Project Structure

```
project/
├── frontend/                  # React + TypeScript + Tailwind
│   └── src/
│       ├── pages/             # One page per use case
│       ├── components/        # Shared UI components
│       ├── services/          # API call functions
│       └── types/             # TypeScript interfaces
├── backend/
│   └── app/
│       ├── api/routes/        # FastAPI route handlers
│       ├── services/          # Business logic (one per use case group)
│       ├── domain/            # Domain entities
│       └── infrastructure/    # Models, repositories, adapters
├── tests/
│   ├── acceptance/
│   │   ├── features/          # Gherkin .feature files (one per UC)
│   │   ├── steps/             # Behave step definitions
│   │   └── support/           # Test doubles, fixture seeder, DB reset
│   └── unit/                  # Pytest unit tests
├── docs/
│   └── UC1–UC10/              # Per-use-case artifacts
│       ├── structured_requirement.md
│       ├── ui_design.md
│       ├── db_design.md
│       └── failure_bundles/
└── ref/                       # Reference documents (use cases, methodology)
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (via `brew install postgresql` on Mac)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm start
```

### Database
```bash
createdb smart_building_dev
cd backend
alembic upgrade head
```

### Run Acceptance Tests
```bash
cd tests
behave acceptance/features/
```

### Run Unit Tests
```bash
cd backend
pytest ../tests/unit/
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
DATABASE_URL=postgresql://localhost/smart_building_dev
ANTHROPIC_API_KEY=your_key_here
```
