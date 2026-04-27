# AGENTS.md

Instructions for any autonomous agent (including the UC Pipeline Automation Agent at `.claude/agents/uc-pipeline-agent.md`) working in this repository.

## 1. Startup Rules

Before writing any code, complete these steps in order:

1. Read this file completely.
2. Read `CLAUDE.md` for codebase conventions and architecture rules.
3. Read `README.md` for project overview, tech stack, and setup.
4. If `ARCHITECTURE.md` exists, read it. (Not present yet — `CLAUDE.md` is the architecture reference for now.)
5. Run `./init.sh` to verify the project builds cleanly.
6. Read `AGENT-PROGRESS.md` to see what the previous session left open.
7. Read `feature_list.json` to see the current pass/fail/in-progress state of all use cases.
8. Read `docs/automation_agent.md` for the agent's design contract.

## 2. Session Policy

When implementing a use case, you MUST follow this workflow:

- Follow the **4-prompt flow pipeline (T1 → T2 → T3 → T4)** as specified in `ref/Acceptance Testing Methodology for AI-Generated Code with UI and DB Integration.pdf` and detailed in `docs/automation_agent.md`.
- Implement only the use case named at session start. Do not touch code unrelated to that use case.
- Pause for human review at each of the five checkpoints defined in `docs/automation_agent.md` §5.
- Never edit a `.feature` file to make a test pass — fix the implementation instead.
- Always use test doubles in `tests/acceptance/support/test_doubles/` during acceptance runs, never real external adapters.
- When a use case's full acceptance suite passes, set its status in `feature_list.json` to `pass` with evidence (last run timestamp + scenario count).
- Draft a commit referencing the use case ID; **wait for human approval before committing or pushing**.

Violating this policy — implementing multiple use cases in one pass, editing files outside the active use case's scope, or pushing without approval — is the most common cause of regressions in this project.

## 3. Scope and Deferral

If part of a use case spec is too expensive for the first pass, document it as a numbered assumption (e.g., `A5: Manual entry deferred — out of scope for UC{N}`) in `docs/UCN/structured_requirement.md`. **Do not create a new use case for deferred scope** — the project's 10 use cases are fixed.

## 4. Discussion Before Fix

When a test fails or a non-trivial design issue surfaces, present:
1. Which scenario failed.
2. Why it's failing (root cause).
3. 2–4 candidate fixes with trade-offs.
4. A recommendation.

Wait for the user to pick before editing code. Trivial fixes (typo, missing import) may be applied directly.

## 5. End of Session

Before ending a session:

- Update `AGENT-PROGRESS.md` with the current state (use the format in that file).
- Update `feature_list.json` with the status of any completed use case (schema in `feature_list.schema.json`).
- Record any unresolved blockers or risks in `AGENT-PROGRESS.md`.
- Draft a commit with a descriptive message once the work is in a safe state. Do not push unless explicitly asked.
- Leave the repo clean enough that the next session can run `./init.sh` immediately.

## 6. Conventions Worth Repeating

- Brief commit messages. No `Co-Authored-By: Claude` trailer.
- React pages stay thin — no business logic.
- Services own all business logic; repositories own all SQL.
- Each UC tracks its test status in `docs/UCN/acceptance_status.md`.
- T2 output splits into three files (`ui_design.md`, `db_design.md`, `harness_design.md`) with explicit Part A–E labels.
