# UC6 AdaptPlanToOccupancyChange — Structured Requirement

## A) Structured Requirement

**Use case name:** AdaptPlanToOccupancyChange

**Participating actors:**
- OccupancyDataService (primary; internal actor that pushes occupancy-change events to the building).
- FacilityManager (secondary; reviews adapted recommendations on the `/adapt-plan` page).
- Adapt Plan Service (control).
- Recommendation Service (reused from UC4 via a new `run_within(building_id, *, db, commit=False)` variant).
- OptimizationAdapter (external; reused from UC4 — a deterministic test double drives acceptance).
- OccupancyStore (DB-backed; `occupancy_records` table — read for baseline, write for new event).
- RecommendationStore (DB-backed; `setpoint_recommendations` table — read for active-plan baseline, write for the new run when material).
- AppliedChangeStore (DB-backed; `applied_setpoint_changes` table — read-only, used to qualify a recommendation run as the "active plan").
- PlanAdaptationEventStore (DB-backed; new `plan_adaptation_events` table — write).

**Goal:** When the OccupancyDataService reports an occupancy change for one or more zones, the system records the new occupancy snapshot, decides whether the change is **material** against the baseline that fed the active plan, and — if material — replans the whole building by reusing UC4 to produce a fresh `setpoint_recommendations` run, all in a single DB transaction. Every adapt request — material or not — appends one `plan_adaptation_events` row capturing the decision, reason, changed zones, and elapsed time. The FacilityManager reviews the revised recommendations through the existing UC4 surface plus a new `/adapt-plan` page that exposes the decision pill, changed-zones list, and revised-recs table.

**Preconditions:**
- A building profile with at least one zone exists (UC1).
- An **active plan** exists for the building — defined as the latest `setpoint_recommendations` run whose ids include ≥1 row in `applied_setpoint_changes` (any status). See A2.
- A baseline `occupancy_records` row exists for each subject zone (else baseline=0 per A3).
- The `OptimizationAdapter` is bound (a deterministic test double during acceptance).
- Forecasts and comfort constraints exist for every zone (preconditions of the reused UC4 path).

**Trigger boundary:** `POST /api/buildings/{building_id}/plan/adapt` with body `{"occupancy_changes": [{"zone_id": int, "new_occupancy_count": int}, ...]}`.

**Main success flow:**
1. OccupancyDataService POSTs an occupancy-change event with one or more `(zone_id, new_occupancy_count)` pairs.
2. System loads the building. Missing → 400 `missingInputs=["building"]`.
3. System validates the payload: empty `occupancy_changes` → 400 `missingInputs=["occupancy_changes"]`; any `zone_id` not belonging to the building → 400 `missingInputs=["zone"]`; atomically (zero side-effects on rejection).
4. System resolves the **active plan** for the building per A2. None → 400 `missingInputs=["active_plan"]`.
5. For every `(zone_id, new_occupancy_count)` pair the service:
   1. Inserts a new `occupancy_records` row for that zone with `timestamp = now()` and `occupancy_count = new_occupancy_count`.
   2. Loads the baseline row for that zone per A3 (latest `occupancy_records` row for the zone, read **before** the row from step 5.1 is inserted, within the same transaction; zero when none).
   3. Computes `delta_fraction = abs(new − baseline) / max(baseline, 1)`. The change is **material** iff `delta_fraction >= MATERIAL_OCCUPANCY_DELTA_FRACTION` (A1). The zero-baseline rule (any positive new value when baseline=0) is material by construction.
6. The service collects the set of `changed_zone_ids` = the zones whose pair was material.
7. If `changed_zone_ids` is empty → record a `plan_adaptation_events` row with `decision='no_replan'`, `reason='no material change'`, `new_run_timestamp=NULL`, `changed_zone_ids=[]`. Commit, return.
8. Else → reuse the recommendation pipeline via `RecommendationService.run_within(building_id, db=db, commit=False)`. The fresh `setpoint_recommendations` rows are flushed to the DB session but **not** committed by the inner service. The outer service then records a `plan_adaptation_events` row with `decision='replanned'`, `reason='material occupancy delta'`, `new_run_timestamp=<inner run_timestamp>`, `changed_zone_ids=[...]`. The outer service commits everything in **one transaction**.
9. The service returns `AdaptPlanResult` carrying `decision`, `reason`, `changed_zone_ids`, `new_run_timestamp` (nullable), `revised_recommendations` (empty on `no_replan`), and `elapsed_ms`.

**Success postconditions:**
- Exactly one `plan_adaptation_events` row per accepted adapt request.
- Exactly one new `occupancy_records` row per pair in the request (regardless of materiality).
- On `decision='replanned'`, a fresh `setpoint_recommendations` run exists for the building with `run_timestamp` strictly greater than the prior active plan's `run_timestamp`.
- On `decision='no_replan'`, no new `setpoint_recommendations` rows are written.
- `GET /api/buildings/{building_id}/plan/adaptations` returns adapt events ordered by `requested_at DESC`.

**Failure postconditions:**
- On validation failure (`building`, `zone`, `occupancy_changes`, `active_plan`): **zero** new `plan_adaptation_events`, `occupancy_records`, or `setpoint_recommendations` rows are written.
- On a DB / inner-service error: transaction rolls back. API returns 500. Zero new rows in any of the three tables.

**Quality requirements:**
- Q1: Materiality test is `delta_fraction >= 0.30` (A1) with zero-baseline rule.
- Q2: A `replanned` outcome end-to-end (5-zone building) completes in under **2000 ms** (S16).
- Q3: Persistence is atomic per request: the new occupancy rows, the optional new recommendation run, and the adapt event commit together (A7).
- Q4: Two identical payloads in sequence produce two events; the second sees zero delta against the new baseline and resolves to `no_replan` (A8 + S14).
- Q5: Adapt requests for building A leave building B's tables untouched (S15).

### Numbered Assumptions

- **A1** Material change is `abs(new − baseline) / max(baseline, 1) >= 0.30`. The threshold lives in `MATERIAL_OCCUPANCY_DELTA_FRACTION = 0.30` (one constant in `app.services.adapt_plan_service`).
- **A2** The **active plan** for a building is the latest `setpoint_recommendations` run (by `run_timestamp DESC`) whose ids include ≥1 matching row in `applied_setpoint_changes`, irrespective of that row's `status` (`dispatched` or `failed`). Force-adapt against an un-applied plan is **deferred**.
- **A3** The baseline occupancy for a zone is the latest `occupancy_records` row for that zone, read **before** the request's new occupancy row is inserted, within the same transaction (read-then-insert ordering). The `active_plan.run_timestamp` is **not** used as a clamp. If no prior row exists → baseline=0; the zero-baseline rule (A1's denominator) then treats any positive new value as material. This ordering is what makes S14 (determinism via identical-payload replay) observe a 0 delta on the second call — the second call's baseline is the row the first call just persisted.
- **A4** Notification of replan is a stdlib `logging.INFO` log line. A real notification channel (email, push, Slack) is **deferred**.
- **A5** Replanning is **whole-building** — the reused UC4 path recomputes every zone. The response surfaces `changed_zone_ids` so the UI can highlight only the zones that crossed the threshold.
- **A6** The OccupancyDataService is an internal actor; the event surface = the POST body. A background poller / push-stream is **deferred**.
- **A7** All writes for one adapt request share a single SQLAlchemy session and commit together. `RecommendationService.run_within(building_id, *, db, commit=False)` is the new in-transaction variant; the existing `run` keeps committing.
- **A8** No idempotency key on adapt requests. Two identical payloads produce two events; determinism is exercised by S14, which observes that the second call sees a zero delta against the freshly-updated baseline and produces `no_replan`.
- **A9** FM review surfaces the revised recommendations through the existing `/recommendations` page (refreshed `latest`) plus a new `/adapt-plan` page that adds the decision pill, reason text, changed-zones list, and a revised-recs table. No new approval workflow.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| Single-zone material change triggers replan | 200 + `decision='replanned'`, 1 new setpoint run, changed_zone_ids=[A] | S01 |
| Multi-zone material change triggers replan; mixed-zone changed list | 200 + `decision='replanned'`, changed_zone_ids = material subset | S02, S03 |
| Non-material change suppresses replan | 200 + `decision='no_replan'`, 0 new setpoint runs, 1 adapt event | S04 |
| Threshold below 30 % is non-material | `decision='no_replan'` at 29 % | S05 |
| Threshold at 30 % is material | `decision='replanned'` at 30 % | S06 |
| Zero-baseline new occupancy is material | replan when baseline=0 → new=5 | S07 |
| Negative direction (drop) is material when ≥30 % | replan when 100→60 | S08 |
| Missing active plan rejected | 400 `missingInputs=["active_plan"]` | S09 |
| Unknown building rejected | 400 `missingInputs=["building"]` | S10 |
| Unknown zone in payload rejected; atomic | 400 `missingInputs=["zone"]`, 0 new rows | S11 |
| Empty occupancy_changes rejected | 400 `missingInputs=["occupancy_changes"]` | S12 |
| Active plan resolves under mixed UC5 applied state | adapt proceeds with `failed` + `dispatched` mix | S13 |
| Determinism on identical repeat | second call observes 0 delta and returns `no_replan` | S14 |
| Cross-building isolation | adapt on A leaves B's tables intact | S15 |
| Performance ceiling | replanned 5-zone building completes <2000 ms | S16 |
| UI flow | `/adapt-plan` page shows banner, decision pill, reason, changed-zones, revised-recs table | S17 |

## C) Acceptance Oracles

- **Decision oracle:** API `decision ∈ {'replanned','no_replan'}` matches the materiality rule (A1) over the supplied payload + the resolved baseline (A3).
- **Persistence oracle (event):** Exactly one `plan_adaptation_events` row per 200 response, with the same `decision`, `changed_zone_ids`, and `new_run_timestamp` as the API.
- **Persistence oracle (occupancy):** Exactly one new `occupancy_records` row per pair in the request, regardless of materiality.
- **Persistence oracle (replan):** When `decision='replanned'`, exactly one new `setpoint_recommendations` run exists with `run_timestamp > active_plan.run_timestamp`. When `decision='no_replan'`, the recommendation table count is unchanged.
- **Atomicity oracle (validation failure):** On 400, the row counts of `plan_adaptation_events`, `occupancy_records`, and `setpoint_recommendations` for the target building are unchanged from before the call.
- **Cross-building oracle:** Building B's row counts are unchanged after an adapt for A.
- **Performance oracle:** Server-reported `elapsed_ms` and client-observed wall-clock both <2000 ms for a 5-zone `replanned` path.
- **UI oracle:** `/adapt-plan` renders `adapt-success-banner` on 200; `adapt-decision-pill` reads `replanned` or `no_replan`; `adapt-reason-text` carries the service-reported reason; one `adapt-changed-zone-{zone_id}` chip per material zone; one `adapt-revised-rec-row-{rank}` per row in the revised run.

## D) Deferred Scope (Recap)

- Real push / poll source for OccupancyDataService events (A6).
- Real notification channel — replan today is a stdlib `INFO` log (A4).
- Idempotency keys on adapt requests (A8).
- Force-adapt against an un-applied plan (A2).
- Per-zone targeted replan (replans are whole-building per A5).
