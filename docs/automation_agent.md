# UC Pipeline Automation Agent — Design Document

## Table of Contents
1. [Agent Overview](#1-agent-overview)
2. [Inputs and Outputs](#2-inputs-and-outputs)
3. [Architecture and Design Structure](#3-architecture-and-design-structure)
4. [Execution Workflow Across the Four Prompt Templates](#4-execution-workflow-across-the-four-prompt-templates)
5. [Review and Human Approval](#5-review-and-human-approval)
6. [How to Use This Agent](#6-how-to-use-this-agent)
7. [Practical Guidelines](#7-practical-guidelines)
8. [Appendix A: Combined Markdown File Structure](#appendix-a-combined-markdown-file-structure)
9. [Appendix B: Mapping to This Project](#appendix-b-mapping-to-this-project)

---

## 1. Agent Overview

The **UC Pipeline Automation Agent** is an autonomous Claude-driven agent that executes the four-template prompt pipeline (T1→T4) defined in *Acceptance Testing Methodology for AI-Generated Code with UI and DB Integration* for a single use case at a time. It transforms a use case specification into:

- a structured requirement and Gherkin scenarios (T1),
- a UI + database + acceptance harness design (T2),
- a runnable implementation that satisfies the Gherkin contract (T3), and
- (when needed) a minimal patch that fixes failing acceptance tests (T4).

The agent enforces the project's **acceptance contract**: a use case is only "done" when its Gherkin scenarios pass against the real implementation through the harness. It refuses to touch files outside the active use case's scope and refuses to weaken `.feature` files to make tests pass.

The agent is implemented as a **Claude Code sub-agent** (markdown definition under `.claude/agents/uc-pipeline-agent.md`) so it runs inside the same toolchain that already drives this repository — no extra runtime, no external orchestrator. It calls the same `Read`/`Edit`/`Write`/`Bash`/`Grep` tools the main session uses.

### Goals
- Reduce per-UC overhead so a developer can run all 10 use cases through the same disciplined flow without re-typing prompts.
- Make the methodology auditable: every UC produces one combined markdown artifact that records the four templates' outputs end-to-end.
- Hard-stop between templates so a human reviews each stage before the agent proceeds.

### Non-Goals
- The agent does **not** implement multiple UCs in one pass.
- The agent does **not** make autonomous repository pushes — it stages commits and asks the user.
- The agent does **not** invent acceptance criteria; if criteria are missing, it asks.

---

## 2. Inputs and Outputs

### 2.1 Inputs

The agent accepts inputs at three levels.

**Project-level (one-time, read from `AGENTS.md` and project root):**
- Tech stack declared in `AGENTS.md` and `README.md` (this project: React + FastAPI + PostgreSQL + Behave + Playwright).
- File-tree conventions from `CLAUDE.md` (services own business logic, repositories own SQL, etc.).
- Existing scaffolding files: `init.sh`, `AGENT-PROGRESS.md`, `feature_list.json`, `feature_list.schema.json`.

**Session-level (read at agent start):**
- `AGENTS.md` — startup rules and session policy.
- `AGENT-PROGRESS.md` — what the previous session left open.
- `feature_list.json` — current pass/fail/in-progress state of all UCs.

**Use case-level (provided by the developer when invoking the agent):**
- A single use case identifier (e.g., `UC3`).
- The use case specification text (or pointer to it in `ref/Project4_UseCases.docx`).
- Acceptance criteria (if not already in the spec).
- Optional constraints (performance budgets, scope deferrals, technology preferences).

### 2.2 Outputs

For each UC the agent produces:

| Artifact | Path | Purpose |
|---|---|---|
| Combined pipeline markdown | `docs/UCN/UCN_pipeline.md` | Full T1→T4 record (assignment requirement) |
| Structured requirement | `docs/UCN/structured_requirement.md` | T1 Part A |
| Gherkin feature file | `tests/acceptance/features/UCN_*.feature` | T1 Part B |
| UI design | `docs/UCN/ui_design.md` | T2 Part A |
| DB design | `docs/UCN/db_design.md` | T2 Part B |
| Harness design | `docs/UCN/harness_design.md` | T2 Parts C–E |
| Implementation code | `backend/app/...`, `frontend/src/...` | T3 |
| Failure bundle (if any) | `docs/UCN/failure_bundles/*.md` | T4 input |
| Acceptance status | `docs/UCN/acceptance_status.md` | Test run record |
| Updated `feature_list.json` | repo root | Use case status flip to `pass` |
| Updated `AGENT-PROGRESS.md` | repo root | Session log |

The **combined pipeline markdown** is the single source of truth required by the assignment. The per-template files (already established by UC1/UC2 convention) are kept for backward compatibility — the combined file references and includes them.

---

## 3. Architecture and Design Structure

### 3.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│           Developer (Claude Code main session)           │
│                          │                               │
│                          │  invokes via Agent tool       │
│                          ▼                               │
│   ┌──────────────────────────────────────────────────┐   │
│   │     UC Pipeline Sub-Agent (uc-pipeline-agent)    │   │
│   │  ───────────────────────────────────────────────  │   │
│   │   Stage Controller                                │   │
│   │      │                                            │   │
│   │      ├─► T1 Stage  ──► writes structured_req +    │   │
│   │      │               feature file, pauses         │   │
│   │      │                                            │   │
│   │      ├─► T2 Stage  ──► writes ui/db/harness,      │   │
│   │      │               pauses                       │   │
│   │      │                                            │   │
│   │      ├─► T3 Stage  ──► writes code, runs behave,  │   │
│   │      │               pauses                       │   │
│   │      │                                            │   │
│   │      └─► T4 Stage  (only if T3 produced failures) │   │
│   │                    minimal patch, re-runs behave  │   │
│   │                                                   │   │
│   │   Combined-Markdown Writer  (appends each stage)  │   │
│   │   feature_list.json Updater                       │   │
│   │   AGENT-PROGRESS.md Updater                       │   │
│   └──────────────────────────────────────────────────┘   │
│                          │                               │
│                          ▼                               │
│            Repository file system + Postgres             │
│            + behave + Playwright + FastAPI + Vite        │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Components

**Stage Controller.** Linear state machine: `INIT → T1 → REVIEW → T2 → REVIEW → T3 → REVIEW → (T4 → REVIEW)? → FINALIZE`. Each transition past a `REVIEW` state requires explicit human approval.

**Template Executors.** One per template. Each executor:
1. Loads the relevant prompt template text (from `ref/Acceptance Testing Methodology...pdf` pages 15–16, 19, 22, 25 respectively).
2. Substitutes use-case context into the prompt's input slots.
3. Produces the prompt's required outputs.
4. Writes per-template files **and** appends a clearly-labelled section to `docs/UCN/UCN_pipeline.md`.

**Combined-Markdown Writer.** Maintains `docs/UCN/UCN_pipeline.md` with the structure shown in [Appendix A](#appendix-a-combined-markdown-file-structure).

**State Updaters.** After T3 (or T4 if invoked), update `feature_list.json` (status `in-progress`→`pass`) and `AGENT-PROGRESS.md` (decisions, files modified, evidence).

**Acceptance Runner.** Wraps `PYTHONPATH="./backend:." behave tests/acceptance/features/UCN_*.feature` and parses Behave's output to detect failures. On failure, packages a *failure bundle* (failing scenario, expected vs actual, relevant logs, code under test) for T4.

### 3.3 Design Principles

- **One UC at a time.** The agent refuses to operate on multiple UCs in a single invocation.
- **Acceptance contract is sacrosanct.** The agent never edits a `.feature` file to make a test pass. It only edits implementation.
- **Test doubles in acceptance runs.** Real adapters are never wired into Behave; the agent uses doubles in `tests/acceptance/support/test_doubles/`.
- **Append-only combined markdown.** Each stage appends; earlier stages are not rewritten so the artifact preserves the methodology trail.
- **No autonomous push.** Commits are drafted; pushes wait for human approval.

---

## 4. Execution Workflow Across the Four Prompt Templates

### 4.1 Initialization
1. Read `AGENTS.md` (startup rules).
2. Run `./init.sh` (verifies dependencies, type checks, build).
3. Read `AGENT-PROGRESS.md` and `feature_list.json`.
4. Confirm the target UC ID with the user. If `feature_list.json` shows it already `pass`, abort.
5. Create `docs/UCN/UCN_pipeline.md` with a header and the use case statement.

### 4.2 Template 1 — Use Case → Structured Requirement + Gherkin
**Goal:** convert the use case into a structured requirement and Gherkin scenarios that form the acceptance contract.

**Steps:**
1. Read prompt T1 (methodology PDF, pp. 15–16).
2. Substitute the use case + acceptance criteria + constraints into T1.
3. Produce:
   - Part A — Structured requirement (actor, preconditions, main flow, alternative flows, post-conditions, data model hints).
   - Part B — Gherkin `.feature` file with one scenario per acceptance criterion plus edge cases.
4. Save:
   - `docs/UCN/structured_requirement.md`
   - `tests/acceptance/features/UCN_<Name>.feature`
   - Append T1 section to `docs/UCN/UCN_pipeline.md`.
5. **Pause for human review.**

### 4.3 Template 2 — Gherkin → UI + DB + Acceptance Harness Design
**Goal:** design the UI surface, persistence layer, and acceptance harness that the Gherkin scenarios will exercise.

**Steps:**
1. Read prompt T2 (methodology PDF, p. 19).
2. Substitute the T1 outputs into T2.
3. Produce three files (per existing convention):
   - `docs/UCN/ui_design.md` — Part A (UI Design Summary, including `data-testid`s for Playwright).
   - `docs/UCN/db_design.md` — Part B (schema additions/changes, migrations, constraints).
   - `docs/UCN/harness_design.md` — Part C (service/control), Part D (acceptance harness — test doubles, environment hooks), Part E (traceability table mapping each Gherkin step to a harness step).
4. Append T2 section to `docs/UCN/UCN_pipeline.md` summarising Parts A–E and linking the three files.
5. **Pause for human review.**

### 4.4 Template 3 — Contract + Design → Integrated Implementation
**Goal:** implement the use case so all Gherkin scenarios pass.

**Steps:**
1. Read prompt T3 (methodology PDF, p. 22).
2. Implement, in order: domain → repository → service → API route → frontend page → step definitions.
3. Add an Alembic migration if DB schema changed.
4. Run the acceptance suite for this UC: `PYTHONPATH="./backend:." behave tests/acceptance/features/UCN_*.feature`.
5. If all scenarios pass → write `docs/UCN/acceptance_status.md`, append T3 section to combined markdown, **pause for human review**, then proceed to finalization.
6. If scenarios fail → package a failure bundle into `docs/UCN/failure_bundles/UCN-S0X_<short>.md` and proceed to T4.

### 4.5 Template 4 — Failure Bundle → Minimal Patch (conditional)
**Goal:** apply the smallest correct fix that resolves the failure bundle without changing the contract.

**Steps:**
1. Read prompt T4 (methodology PDF, p. 25).
2. Diagnose the root cause from the failure bundle.
3. Propose 2–4 candidate fixes with trade-offs and a recommendation. **Pause for human selection.**
4. Apply the chosen patch. Do not edit `.feature` files.
5. Re-run the acceptance suite. If still failing, package a new failure bundle and loop.
6. On pass: append T4 section to combined markdown, update `acceptance_status.md` (T4 cycle count + bundle path), **pause for human review**.

### 4.6 Finalization
1. Run the full regression: `PYTHONPATH="./backend:." behave tests/acceptance/features/`.
2. Update `feature_list.json`: set this UC's status to `pass` with evidence.
3. Update `AGENT-PROGRESS.md`: log decisions, files modified, evidence.
4. Draft a commit message referencing the UC ID. **Ask the user before committing or pushing.**

---

## 5. Review and Human Approval

The agent enforces five mandatory human checkpoints per UC:

| # | After stage | What the human reviews | What the agent waits for |
|---|---|---|---|
| 1 | T1 | Structured requirement + Gherkin scenarios | "approved" / edits requested |
| 2 | T2 | UI/DB/harness design | "approved" / edits requested |
| 3 | T3 (pass) | Implementation diff + Behave run output | "approved" / edits requested |
| 4 | T4 option selection | Failure root cause + candidate fixes | choice of fix |
| 5 | Finalization | Regression result + drafted commit | commit/push approval |

**Discussion-before-fix rule.** When tests fail, the agent presents *which scenario failed*, *why*, *2–4 candidate fixes with trade-offs*, and *a recommendation*. It does not edit code until the developer picks an option. (This rule is encoded in the project's memory and is non-negotiable.)

**Scope-deferral rule.** If part of a UC spec is too expensive for the first pass, the agent records it as a numbered assumption in `structured_requirement.md` (e.g., `A5: Manual entry deferred — out of scope for UC{N}`). It does **not** create a new UC; the project's 10 UCs are fixed.

---

## 6. How to Use This Agent

### 6.1 Prerequisites
- Repo cloned, `./init.sh` runs cleanly.
- Postgres `smart_building_dev` and `smart_building_test` databases exist.
- `.venv` activated; Node deps installed.
- `feature_list.json` reflects current state of all 10 UCs.

### 6.2 Invoking the Agent

From the Claude Code main session:

```
> Run uc-pipeline-agent on UC3.
```

Claude Code will spawn the sub-agent. The sub-agent will:
1. Read `AGENTS.md`, `AGENT-PROGRESS.md`, `feature_list.json`.
2. Confirm UC3 is the target and is not already `pass`.
3. Walk through T1 → review → T2 → review → T3 → (T4) → finalization, pausing for approval at each checkpoint.

### 6.3 Resuming After a Pause
At each checkpoint the agent prints a summary and the path to the artifacts to review. Reply with:
- `approved` — agent proceeds to next stage.
- `edits: <description>` — agent revises and re-presents.
- `abort` — agent stops; partial artifacts remain on disk for inspection.

### 6.4 Recovering From a Crash
If the session ends mid-pipeline:
1. Re-run `./init.sh`.
2. Read `AGENT-PROGRESS.md` to see the last completed stage.
3. Re-invoke the agent on the same UC; it resumes from the last completed stage based on which artifact files exist on disk.

---

## 7. Practical Guidelines

1. **Never weaken the contract.** If a Gherkin scenario seems wrong, fix the spec or add a new scenario — do not delete or relax steps to make a build green.
2. **Keep test doubles isolated.** `tests/acceptance/support/test_doubles/` is the only place real adapters are stubbed for acceptance tests. Production code never reads that directory.
3. **Repository pattern is enforced.** Services never write SQL; routes never contain business logic; React pages stay thin.
4. **One commit per UC stage transition.** The agent drafts: `UCN T1-T2: ...`, `UCN T3: ...`, `UCN T4: ...` and lets the developer batch as desired.
5. **Combined markdown is append-only.** Once a section is written, later stages add new sections rather than rewriting earlier ones — this preserves the methodology audit trail.
6. **The acceptance suite must be green before commit.** The agent refuses to mark `pass` in `feature_list.json` until `behave tests/acceptance/features/UCN_*.feature` exits 0.
7. **Memory hygiene.** The agent does not write to the project memory store; that remains the main session's responsibility.
8. **Brief commit messages.** No `Co-Authored-By: Claude` trailer. Reference the UC ID in the subject.

---

## Appendix A: Combined Markdown File Structure

`docs/UCN/UCN_pipeline.md` follows this template:

```markdown
# UCN <Name> — Full Pipeline Record

## Metadata
- Use Case ID: UCN
- Started: YYYY-MM-DD HH:MM
- Last updated: YYYY-MM-DD HH:MM
- Status: in-progress | pass

## Use Case Statement
<verbatim from spec>

## Acceptance Criteria
<numbered list>

---

## T1 — Structured Requirement and Gherkin
### Part A) Structured Requirement
<full content, also stored in docs/UCN/structured_requirement.md>

### Part B) Gherkin
<full content, also stored in tests/acceptance/features/UCN_*.feature>

---

## T2 — UI, DB, and Harness Design
### Part A) UI Design Summary
<see docs/UCN/ui_design.md — full content embedded>

### Part B) Database Design Summary
<see docs/UCN/db_design.md — full content embedded>

### Part C) Service / Control
<see docs/UCN/harness_design.md — Part C embedded>

### Part D) Acceptance Harness
<Part D embedded>

### Part E) Traceability Table
<Part E embedded>

---

## T3 — Implementation
### Files Created/Modified
<bulleted list with one-line description per file>

### Acceptance Run
<command + Behave output summary: N/N scenarios pass>

---

## T4 — Failure Bundle and Patch (only if needed)
### Failure Bundle
<bundle content or link>

### Candidate Fixes Considered
<options with trade-offs>

### Chosen Fix
<one-paragraph rationale>

### Patch Applied
<diff summary>

### Re-run Result
<command + output>

---

## Finalization
- feature_list.json: status flipped to "pass"
- AGENT-PROGRESS.md: updated
- Regression: M/M scenarios across all completed UCs pass
- Commit: <hash and message>
```

---

## Appendix B: Mapping to This Project

| Methodology concept | This project's realization |
|---|---|
| Acceptance contract | `tests/acceptance/features/UCN_*.feature` (Behave) |
| UI surface | React pages under `frontend/src/pages/` |
| Service / Control | `backend/app/services/<feature>_service.py` |
| Repository / Persistence | `backend/app/infrastructure/repositories/` |
| Domain entities | `backend/app/domain/` |
| Test doubles | `tests/acceptance/support/test_doubles/` |
| Harness environment | `tests/acceptance/environment.py` |
| Database (test mode) | `smart_building_test` (via `TESTING=1`) |
| Step definitions | `tests/acceptance/steps/UCN_steps.py` |
| Migrations | `backend/alembic/versions/` |

The agent honors the existing 3-file T2 split (per project memory) **in addition to** writing the combined `UCN_pipeline.md` required by the assignment.
