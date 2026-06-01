# UC4 RecommendHVACSetpointChanges — Structured Requirement

## A) Structured Requirement

**Use case name:** RecommendHVACSetpointChanges

**Participating actors:**
- FacilityManager (primary, initiates a recommendation run from the UI or API)
- Recommendation Service (control)
- OptimizationAdapter (external; encapsulates the optimization model — MILP / RL / heuristic)
- Forecasting Service (upstream producer; UC3 — read-only)
- ZoneComfortConstraintsStore (DB-backed; comfort bounds per zone)
- Plan Approval / Dispatch service (downstream consumer — UC5, out of scope here)

**Goal:** Given the most recent zone-level demand forecasts (UC3) and per-zone comfort constraints, produce a ranked list of HVAC setpoint-change recommendations per zone, persist them as a single recommendation run, and expose the run to the FacilityManager so that an approved plan can later be dispatched (UC5).

**Preconditions:**
- A building profile with at least one zone exists (UC1).
- For every zone of the building, a fresh demand forecast exists (UC3) — "fresh" meaning the latest forecast's `timestamp` is within the last 24 hours of the run timestamp.
- For every zone of the building, a `zone_comfort_constraints` row exists.
- The `OptimizationAdapter` is bound (a deterministic test double during acceptance — see A3).

**Trigger boundary:** `POST /api/buildings/{building_id}/recommendations/run` (see A4).

**Main success flow:**
1. FacilityManager triggers a recommendation run for a target building.
2. System loads the building and its zones. If the building does not exist → fail with `missingInputs=["building"]`. If the building has zero zones → fail with `missingInputs=["zones"]`.
3. For each zone, the system loads the latest `demand_forecasts` row (UC3). If any zone is missing a forecast, or the latest forecast for any zone is older than 24 hours relative to the run timestamp → fail with `missingInputs=["forecast"]`.
4. For each zone, the system loads the `zone_comfort_constraints` row. If any zone has no comfort constraints → fail with `missingInputs=["comfort_constraints"]`.
5. For each zone, the system calls `OptimizationAdapter.recommend(zone_id, forecast, constraints)`. The adapter returns 0..N candidate setpoint changes. Each candidate is a tuple `(setpoint_delta_f, projected_savings_kwh, comfort_impact, model_version)`.
6. The service filters out infeasible candidates: a candidate is infeasible if applying `setpoint_delta_f` to the zone's current/default setpoint would produce a new setpoint outside `[min_setpoint_f, max_setpoint_f]`. (For the acceptance harness the "current setpoint" baseline is the midpoint of `[occupied_min_f, occupied_max_f]`; see A1.)
7. The service ranks all surviving candidates across all zones in descending order of `projected_savings_kwh`. Ties are broken by `(zone_id ASC, setpoint_delta_f ASC)` (A7).
8. The service stamps each surviving candidate with `run_timestamp = now(UTC)`, `rank = 1..K` (matching the sort order above), `building_id`, `zone_id`, and `model_version`, then persists them as `setpoint_recommendations` rows in a single transaction.
9. The system returns a `RecommendationRunResult` listing the ranked recommendations and the total processing time.

**Success postconditions:**
- One `setpoint_recommendations` row per surviving candidate exists for the run timestamp.
- The run is observable via `GET /api/buildings/{id}/recommendations/latest`, which returns rows ordered by `rank ASC`.
- `elapsed_ms` is reported.

**Failure postconditions:**
- No `setpoint_recommendations` rows are written for the failed run (atomic — all or nothing).
- A structured 400 error identifies missing input(s): `building` | `zones` | `forecast` | `comfort_constraints`.
- Any prior `setpoint_recommendations` rows for this building (from earlier successful runs) remain untouched.

**Quality requirements:**
- Q1: Each persisted row carries `building_id`, `zone_id`, `run_timestamp`, `setpoint_delta_f`, `projected_savings_kwh`, `comfort_impact`, `rank`, and `model_version`.
- Q2: A recommendation run for a building with ≤ 10 zones completes in under **5000 ms** end-to-end.
- Q3: Recommendation persistence is atomic per run — partial persistence is forbidden.
- Q4: The returned ranking is monotonically non-increasing in `projected_savings_kwh`.
- Q5: For a fixed `(building, forecasts, constraints, adapter)` input tuple, two consecutive runs return identical ranked outputs (determinism guaranteed by the deterministic optimization-adapter double).

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| FacilityManager triggers recommendation run | `POST /api/buildings/{id}/recommendations/run` returns 200 with structured run result | S01, S02, S03 |
| System loads zones | Service iterates over building.zones; empty -> 400 ["zones"] | S12 |
| System loads fresh forecasts | Latest demand_forecast per zone, age <= 24h | S01, S08, S09 |
| System loads comfort constraints | Service queries zone_comfort_constraints per zone | S01, S10 |
| System invokes OptimizationAdapter per zone | Adapter called once per zone with `(forecast, constraints)` | S01, S02, S03 |
| Infeasible candidates filtered | Candidates whose new setpoint exits `[min, max]` are dropped | S07 |
| Recommendations ranked by savings DESC | Output `projected_savings_kwh` is monotonically non-increasing | S04 |
| Numeric savings >= 0 | Every surviving candidate has `projected_savings_kwh >= 0` | S05 |
| Comfort impact enum | Every row's `comfort_impact` in {none, minor, moderate} | S06 |
| Persistence atomic | One row per surviving candidate; failure -> 0 rows | S01, S08, S10, S13 |
| Latest run readable | `GET /api/buildings/{id}/recommendations/latest` returns ranked rows of the most recent run | S01, S03 |
| Missing forecast | 400 with `missingInputs=["forecast"]`, 0 rows | S08 |
| Stale forecast (>24h) | 400 with `missingInputs=["forecast"]`, 0 rows | S09 |
| Missing comfort constraints | 400 with `missingInputs=["comfort_constraints"]`, 0 rows | S10 |
| Unknown building id | 400 with `missingInputs=["building"]` | S11 |
| Empty building | 400 with `missingInputs=["zones"]`, 0 rows | S12 |
| Failure preserves prior rows | Prior recommendation rows are unchanged after a failed run | S13 |
| Cross-building isolation | A run on building A does not touch building B's recommendations | S14 |
| Determinism | Two consecutive runs produce identical ranked rows | S15 |
| Performance budget | Run for <=10 zones completes in < 5000 ms | S16 |
| UI error gating | Missing constraints -> error banner, 0 rendered rows, run button re-enabled | S17 |

## C) Acceptance Oracles

- **UI happy-path oracle:** RecommendationsPage lists per-rank rows with `zone_name`, `setpoint_delta_f`, `projected_savings_kwh`, `comfort_impact` after a successful run, in rank order.
- **UI error oracle:** On a failed UI-initiated run, `[data-testid="recommendation-run-error"]` is rendered, `[data-testid="recommendation-missing-inputs"]` contains the missing-input label, no `[data-testid^="recommendation-row-"]` elements are present, and `[data-testid="recommendation-run-button"]` is re-enabled.
- **Persistence oracle:** `setpoint_recommendations` table contains exactly N rows for the latest run, where N is the number of surviving candidates.
- **Ranking oracle:** The `projected_savings_kwh` sequence over rows ordered by `rank ASC` is monotonically non-increasing; ties broken by `(zone_id ASC, setpoint_delta_f ASC)`.
- **Atomicity oracle:** On failure, the count of `setpoint_recommendations` rows for the building equals the count before the failed run.
- **Cross-building isolation oracle:** A run on building A leaves building B's recommendation row count and contents unchanged.
- **Field-structure oracle:** Each row exposes `building_id`, `zone_id`, `run_timestamp`, `setpoint_delta_f`, `projected_savings_kwh`, `comfort_impact` in {none, minor, moderate}, `rank >= 1`, and a non-empty `model_version`.
- **Determinism oracle:** For a fixed adapter + inputs, two consecutive runs produce identical `(zone_id, setpoint_delta_f, projected_savings_kwh, comfort_impact, rank)` tuples.
- **Performance oracle:** Server-reported and client-observed elapsed time both under 5000 ms for <= 10 zones.
- **Error oracle:** On missing input, response body includes `missingInputs` array containing exactly one of `building | zones | forecast | comfort_constraints` (the first failing check).

## D) Assumptions

- **A1:** Comfort constraints (`min_setpoint_f`, `max_setpoint_f`, occupied/unoccupied bands) live in a new `zone_comfort_constraints` table keyed by `zone_id`. A constraints-editor UI is **deferred** — for acceptance, constraints are seeded via a test-only control endpoint. The "current/default setpoint" baseline for feasibility filtering is the midpoint of `[occupied_min_f, occupied_max_f]`; an explicit `current_setpoint` source is deferred to UC5.
- **A2:** Forecast staleness threshold is fixed at **> 24 hours** relative to the run timestamp. Any older forecast triggers `missingInputs=["forecast"]`. A configurable threshold is out of scope.
- **A3:** The optimization engine is encapsulated behind an `OptimizationAdapter` Protocol. Acceptance runs use a deterministic test double (`tests/acceptance/support/test_doubles/optimization_adapter_double.py`) producing fixed `(setpoint_delta_f, projected_savings_kwh, comfort_impact)` tuples per zone. A real MILP / RL backend is **deferred**.
- **A4:** Although the trigger is conceptually "FacilityManager-initiated", the acceptance contract exercises the boundary via the HTTP endpoint `POST /api/buildings/{id}/recommendations/run`. A dedicated scheduler / job orchestration layer is out of scope.
- **A5:** `comfort_impact` is a closed enum `{none, minor, moderate}`. Continuous-valued comfort scoring (PMV, PPD, etc.) is **deferred**.
- **A6:** Approval workflow and downstream device dispatch are **UC5** and are out of scope for UC4. UC4 only persists candidate recommendations; it does not change device state.
- **A7:** Ranking tie-breaker is `(zone_id ASC, setpoint_delta_f ASC)`. Where two candidates share the same `projected_savings_kwh`, the smaller `zone_id` ranks higher; further ties break on the smaller `setpoint_delta_f`.
