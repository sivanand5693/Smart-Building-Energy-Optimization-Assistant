# UC5 ApplyApprovedEnergyPlan — Structured Requirement

## A) Structured Requirement

**Use case name:** ApplyApprovedEnergyPlan

**Participating actors:**
- FacilityManager (primary; selects a subset of the latest UC4 run and submits it for application).
- Apply Plan Service (control).
- DeviceControlAdapter (external; dispatches setpoint changes to a zone-level HVAC device controller — wrapped by a Protocol; a deterministic test double drives acceptance).
- RecommendationStore (DB-backed; the `setpoint_recommendations` table from UC4 — read-only).
- DeviceStore (DB-backed; `devices` table — read-only, filtered to `device_type='hvac'`).
- AppliedChangeStore (DB-backed; new `applied_setpoint_changes` table — write).

**Goal:** Given the latest UC4 recommendation run for a building, the FacilityManager approves a subset of its rows by id. The system dispatches each approved recommendation's setpoint change to the zone's HVAC device controller via the DeviceControlAdapter, and persists a per-recommendation row in `applied_setpoint_changes` (success or failure) in a single DB transaction. The FacilityManager then sees a per-recommendation execution summary.

**Preconditions:**
- A building profile with at least one zone exists (UC1).
- A successful UC4 recommendation run exists for the building (so `setpoint_recommendations` rows exist; the "latest" run is identified by the most recent `run_timestamp` for the building).
- Each zone of the building has at least one HVAC device row (`devices.device_type='hvac'`).
- The `DeviceControlAdapter` is bound (a deterministic test double during acceptance — see A5).

**Trigger boundary:** `POST /api/buildings/{building_id}/plans/apply` with body `{"recommendation_ids": [int, int, ...]}`.

**Main success flow:**
1. FacilityManager triggers an apply request listing the recommendation ids they approve.
2. System loads the building. Missing → 400 `missingInputs=["building"]`.
3. System loads the latest UC4 run for the building (set of `setpoint_recommendations` rows whose `run_timestamp` equals the building's most recent `run_timestamp`).
4. For each id in `recommendation_ids` the system validates that the row exists, belongs to the building, AND is part of the latest run. If any id is unknown / belongs to a different building → 400 `missingInputs=["recommendation"]`. If any id belongs to the building but to an earlier run → 400 `missingInputs=["stale_run"]`.
5. The approved recommendations are processed in ascending `rank` order. For each one:
   1. The service finds the first HVAC device for the zone (`devices.device_type='hvac'`, lowest id). If none → record a `failed` row with `error_code='missing_device'` and continue.
   2. The service checks whether an `applied_setpoint_changes` row already exists for that `recommendation_id`. If so → record a `failed` row with `error_code='already_applied'` and continue. **The adapter is NOT invoked in this case.**
   3. The service calls `DeviceControlAdapter.dispatch(device_id, zone_id, setpoint_delta_f, run_timestamp)`. The adapter returns `(status, adapter_message, latency_ms)` where `status ∈ {dispatched, failed}` and on failure carries an `error_code` (e.g. `adapter_error`).
   4. The service appends one `applied_setpoint_changes` row to the pending batch using the adapter outcome.
6. After every approved recommendation is processed, the service commits all rows in **one transaction**. On a DB error the transaction is rolled back (zero new rows) and the API returns 500.
7. The service returns `ApplyPlanRunResult` listing per-recommendation outcomes plus an `elapsed_ms`.

**Success postconditions:**
- One `applied_setpoint_changes` row per approved `recommendation_id` exists (success or failure alike).
- The `applied_setpoint_changes.recommendation_id` UNIQUE constraint enforces idempotency at the DB layer; the service short-circuits before that constraint fires.
- `GET /api/buildings/{building_id}/plans/latest` returns those rows ordered by `applied_at ASC, id ASC`.

**Failure postconditions:**
- On validation failure (building/recommendation/stale_run): **zero** new `applied_setpoint_changes` rows are written; any rows from earlier successful applies remain intact.
- On DB error during commit: **zero** new rows are written (transaction rolled back); API returns 500.

**Quality requirements:**
- Q1: Each persisted row carries `recommendation_id` (UNIQUE), `building_id`, `zone_id`, `applied_at`, `setpoint_delta_f`, `status ∈ {dispatched, failed}`, optional `error_code`, `adapter_message`, `latency_ms`.
- Q2: An apply batch of ≤ 10 recommendations completes in under **10000 ms** end-to-end.
- Q3: Persistence is atomic per batch: either every per-line row is committed or none are.
- Q4: Per-line failures do not abort sibling successes — the API still returns 200 with mixed `dispatched`/`failed` outcomes.
- Q5: Re-applying an already-applied recommendation does **not** re-dispatch to the adapter; it short-circuits to a `failed` row with `error_code='already_applied'`.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| FacilityManager triggers apply with selected ids | `POST /api/buildings/{id}/plans/apply` returns 200 with per-line outcomes | S01, S02, S03 |
| Single-rec happy path | One `dispatched` row, adapter called once | S01 |
| Multi-rec happy path with rank-ASC ordering across zones | Adapter call order matches rank ASC; N dispatched rows persisted | S02 |
| Approve-all of latest run | Body length matches latest-run length | S03 |
| Single-zone boundary | Approve-all single-zone yields 1 dispatched row | S04 |
| Multi-zone boundary | Approve-all multi-zone yields N dispatched rows | S05 |
| Field structure | Each row exposes `recommendation_id`, `status`, `error_code`, `adapter_message`, `latency_ms`, `setpoint_delta_f`, `zone_id` | S06 |
| Unknown building | 400 `missingInputs=["building"]`, 0 rows | S07 |
| Unknown rec id | 400 `missingInputs=["recommendation"]`, 0 rows | S08 |
| Cross-building rec id | 400 `missingInputs=["recommendation"]`, 0 rows | S09 |
| Idempotency on re-apply | Second apply for same rec → `failed`/`already_applied`; adapter NOT re-invoked | S10 |
| Stale run | Approve rec from an earlier run while a newer run exists → 400 `missingInputs=["stale_run"]`, 0 rows | S11 |
| Missing HVAC device | Apply with zone lacking HVAC → that line `failed`/`missing_device`; siblings still `dispatched` | S12 |
| Adapter failure tolerated | Adapter `failed` for one line → that line `failed`/`adapter_error`; siblings `dispatched` | S13 |
| Cross-building isolation | Apply on A does not write rows for B | S14 |
| DB-error atomicity | Forced DB error → 500, zero new rows | S15 |
| Performance | Apply of 10 recs < 10000 ms server + client | S16 |
| UI execution summary | ApplyPlanPage shows per-line status pills, error labels, success banner | S17 |

## C) Acceptance Oracles

- **Success oracle:** API returns 200 with `results: [...]` of length == len(`recommendation_ids`). Each result row carries `recommendation_id`, `zone_id`, `setpoint_delta_f`, `status`, `error_code` (nullable), `adapter_message`, `latency_ms`.
- **Persistence oracle:** `applied_setpoint_changes` row count for the building equals the number of API result rows; statuses match.
- **Atomicity oracle (validation failure):** On 400, the count of `applied_setpoint_changes` rows for the building is unchanged from before the call.
- **Atomicity oracle (DB error):** On 500, the count of `applied_setpoint_changes` rows for the building is unchanged from before the call.
- **Idempotency oracle:** A second apply containing an already-applied rec_id produces a `failed`/`already_applied` row AND the underlying adapter is called exactly once across both apply attempts for that rec_id.
- **Rank-order oracle:** When multiple rec_ids are applied together, the order of adapter invocations matches their `rank ASC`.
- **Cross-building oracle:** Applying for building A leaves B's `applied_setpoint_changes` count and contents untouched.
- **UI oracle:** ApplyPlanPage renders one `apply-result-row-N` per result; `apply-status-N` reflects status; `apply-error-N` carries the `error_code` label for failed rows; `apply-success-banner` visible when any row is `dispatched`; `apply-error-banner`+`apply-missing-inputs` rendered on 400.
- **Performance oracle:** Server-reported and client-observed elapsed time both under 10000 ms for ≤ 10 recommendations.

## D) Assumptions

- **A1:** "Approval" of a recommendation is implicit via inclusion in the `recommendation_ids` list submitted to the apply endpoint. A separate approval entity / approval-history audit log is **deferred**.
- **A2:** Only recommendations from the **latest** UC4 run can be applied. If any approved id belongs to an earlier run (even if to the same building) → 400 `missingInputs=["stale_run"]`. A "force-apply old plan" mode is out of scope.
- **A3:** Idempotency is enforced by a UNIQUE constraint on `applied_setpoint_changes.recommendation_id`. The service short-circuits before the constraint fires by checking the table; the resulting row is `failed`/`already_applied`, and the adapter is **not** re-invoked.
- **A4:** Partial-apply behavior is "per-line failures persist; sibling successes still commit; whole batch in one txn". A DB error rolls back **everything** in the batch.
- **A5:** The `DeviceControlAdapter` is a Protocol with a deterministic test double at `tests/acceptance/support/test_doubles/device_control_double.py`. The double is programmable per scenario via the test-only endpoint `POST /api/_test/device_control/directive` (`{recommendation_id, outcome: "dispatched"|"failed", error_code?, adapter_message?, latency_ms?}`). Real device-protocol integration (BACnet, Modbus, vendor SDK) is **deferred**.
- **A6:** Device selection per zone = first `devices` row for that zone with `device_type='hvac'` (lowest `id`). Multi-device arbitration, device-availability gating, and explicit primary-device tagging are **deferred**.
- **A7:** `latency_ms` is the adapter-reported per-dispatch latency, supplied by the double during acceptance. Real instrumentation, retries, and timeout policy are **deferred**.
- **A8:** Closed-loop feedback after apply (verifying the device actually reached the new setpoint), adaptive replanning when occupancy diverges (UC6), and comfort-violation risk surfacing (UC7) are out of scope for UC5.
- **A9:** No authentication / authorization in the acceptance harness — the FacilityManager identity is implicit.
