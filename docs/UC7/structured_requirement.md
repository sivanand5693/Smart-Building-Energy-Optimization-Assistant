# UC7 DetectComfortViolationRisk — Structured Requirement

## A) Structured Requirement

**Use case name:** DetectComfortViolationRisk

**Participating actors:**
- Scheduler (primary; internal system actor that fires the detection run).
- FacilityManager (secondary; reviews alerts on the `/comfort-risk` page).
- Comfort Monitoring Service (control).
- DeviceStateAdapter (external; reused from UC3/UC4 — deterministic test double drives acceptance, supplies `setpoint_f` per zone).
- SetpointRecommendationStore (DB-backed; `setpoint_recommendations` table — read-only).
- ZoneComfortConstraintStore (DB-backed; `zone_comfort_constraints` table — read-only).
- ComfortRiskRunStore (DB-backed; new `comfort_risk_runs` table — write).
- ComfortRiskAlertStore (DB-backed; new `comfort_risk_alerts` table — write).

**Goal:** When the Scheduler triggers a comfort-risk detection run for a building, the system retrieves the projected zone temperature for each zone (current setpoint plus the latest planned setpoint delta), compares the projection against that zone's occupied comfort band, computes a normalized risk score in [0, 1], and persists either (a) one `comfort_risk_runs` row with `decision='alert'` plus one `comfort_risk_alerts` row per at-risk zone (score ≥ 0.5) carrying the projected temperature, the band, the risk score, the band-direction tag, and a templated mitigation suggestion; or (b) one `comfort_risk_runs` row with `decision='pass'` and zero alert rows when every evaluated zone is inside its band. Every successful run also reports an `elapsed_ms` server-side. The FacilityManager reviews the result on the new `/comfort-risk` page (decision pill, alert rows, pass message).

**Preconditions:**
- A building profile with at least one zone exists (UC1).
- At least one prior `setpoint_recommendations` run exists for the building (UC4) — this is the "active or proposed energy plan" per A3.
- For each evaluated zone, both a row in `zone_comfort_constraints` (UC4 seed) and a `DeviceStateAdapter.current_for_zone()` payload carrying `setpoint_f` (UC3 double, extended) are available. Missing data on a single zone is **skipped** silently per A2; missing data on **every** zone surfaces as 400 `missingInputs=["comfort_constraints"]` (S11 collapse case).

**Trigger boundary:** `POST /api/buildings/{building_id}/comfort-risk/run` (no body).

**Main success flow:**
1. The Scheduler POSTs the detection run endpoint for the target building.
2. The system loads the building. Missing → 400 `missingInputs=["building"]`.
3. The system resolves the latest `setpoint_recommendations.run_timestamp` for the building (A3). None → 400 `missingInputs=["plan"]`.
4. For each zone in the building (in `zones.id ASC` order for determinism):
   1. Read the latest `setpoint_recommendations` row for that zone in the resolved run (`setpoint_delta_f`). If absent → skip the zone (A2; S10).
   2. Read `zone_comfort_constraints.{occupied_min_f, occupied_max_f}` for that zone. If absent → skip the zone (A2; S11 partial case).
   3. Read `DeviceStateAdapter.current_for_zone(zone_id).setpoint_f`. If absent → skip the zone (A2; S12).
   4. Compute `projected = current_setpoint_f + setpoint_delta_f`.
   5. Compute `band_width = occupied_max_f − occupied_min_f` (zero band → skip; defensive, not in scenarios).
   6. Compute `risk = max(0, max(projected − occupied_max_f, occupied_min_f − projected)) / band_width`, clipped to `[0, 1]`. The zone is **at-risk** iff `risk >= COMFORT_RISK_THRESHOLD` (A1; `0.5`).
   7. If at-risk: tag `direction='above'` when projected > occupied_max_f, else `'below'`. Compute the templated mitigation per A4.
5. Build the list of at-risk-zone alerts (zone_id ASC).
6. If the list is non-empty → `decision='alert'`, `alerts_count = len(alerts)`. Else → `decision='pass'`, `alerts_count = 0`.
7. Insert one `comfort_risk_runs` row + N `comfort_risk_alerts` rows in a single SQLAlchemy transaction (A6). Stamp `source_run_timestamp = active_run_timestamp`, `elapsed_ms` server-measured.
8. Log `comfort_risk_pass` at INFO when `decision='pass'`, `comfort_risk_alert` at INFO when `decision='alert'` (A8).
9. Return `ComfortRiskRunResult` carrying `decision`, `alerts`, `source_run_timestamp`, `elapsed_ms`.

**Success postconditions:**
- Exactly one new `comfort_risk_runs` row per accepted run, with matching `decision`, `alerts_count`, and `source_run_timestamp`.
- Exactly N new `comfort_risk_alerts` rows where N = number of at-risk zones.
- Skipped zones produce zero rows.
- `GET /api/buildings/{building_id}/comfort-risk/latest` returns the most recent `comfort_risk_runs` row + its alerts.

**Failure postconditions:**
- On validation failure (`building`, `plan`, `comfort_constraints` collapse case): zero new `comfort_risk_runs` and zero `comfort_risk_alerts` rows.
- On a DB / inner-service error mid-write: transaction rolls back. API returns 500. Zero new rows in either table.

**Quality requirements:**
- Q1: Risk score is a measurable numeric field stored in `comfort_risk_alerts.risk_score (Numeric(4,3))` (A1).
- Q2: Detection latency target — server-reported `elapsed_ms < 3000` for a 5-zone building (A7; S15).
- Q3: Persistence is atomic per run (A6; S14).
- Q4: Two runs back-to-back over identical fixtures produce alert rows with identical `risk_score`, `direction`, `mitigation` (A9; S16).
- Q5: Runs scoped to a building never touch other buildings' tables (S13).

### Numbered Assumptions

- **A1** Risk = `max(0, max(projected − occupied_max_f, occupied_min_f − projected)) / band_width` clipped to `[0, 1]`; at-risk iff `risk >= COMFORT_RISK_THRESHOLD`. `COMFORT_RISK_THRESHOLD = Decimal("0.5")` lives as a module constant in `app.services.comfort_risk_service`.
- **A2** "Projected zone temperature" = `current_setpoint_f + setpoint_delta_f`. `current_setpoint_f` comes from `DeviceStateAdapter.current_for_zone(zone_id).setpoint_f` (the UC3 double, extended to carry `setpoint_f`). `setpoint_delta_f` is the latest `setpoint_recommendations` row for the zone in the resolved active-or-proposed run. When **either** input is missing for a zone, the zone is **silently skipped** — neither alert nor pass row is generated for it. The run as a whole still completes (assuming at least one zone is evaluable; otherwise see A3/S11 collapse rule).
- **A3** "Active or proposed energy plan" = the latest `setpoint_recommendations` run for the building (by `run_timestamp DESC`), irrespective of `applied_setpoint_changes` state. This deliberately differs from UC6's "active plan" definition because UC7's spec lists "active **or proposed**". No active-plan-application requirement.
- **A4** Mitigation is a templated natural-language string:
  - Above band → `"Reduce setpoint by {N}°F to return to comfort band."` where `N = round(projected − occupied_max_f, 0.5)`.
  - Below band → `"Increase setpoint by {N}°F to return to comfort band."` where `N = round(occupied_min_f − projected, 0.5)`.
  Rounding uses half-up to the nearest 0.5°F. LLM-generated mitigations are **deferred**.
- **A5** The Scheduler is modeled as an internal actor; the event surface = the POST. A background cron is **deferred**.
- **A6** All writes — one `comfort_risk_runs` row plus the N `comfort_risk_alerts` rows — share a single SQLAlchemy session transaction and commit together. Any failure rolls the whole run back.
- **A7** Q2 ceiling: server-reported `elapsed_ms < 3000` on a 5-zone replanned path (S15). Both server and client wall-clock measured for parity.
- **A8** Notification path on `decision='pass'` is a stdlib `logging.INFO` line (`"comfort_risk_pass"`). Real notification channels (email, push, Slack) are **deferred**.
- **A9** No idempotency on runs; two back-to-back runs against the same fixtures write two `comfort_risk_runs` rows and 2×N alert rows. Determinism is exercised by S16, which asserts that `risk_score`, `direction`, and `mitigation` agree row-for-row across runs.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| Above-band projection produces an `above` alert | 200 + `decision='alert'`, 1 alert with `direction='above'` and Reduce mitigation | S01 |
| Below-band projection produces a `below` alert | 200 + `decision='alert'`, 1 alert with `direction='below'` and Increase mitigation | S02 |
| Multi-zone mixed evaluation | 1 above + 1 below + 1 within → `decision='alert'`, 2 alerts | S03 |
| All-within-band → pass | `decision='pass'`, 0 alerts, 1 `comfort_risk_runs` row | S04 |
| Risk boundary just-below 0.50 is not alerted | `risk≈0.49` → no alert for that zone | S05 |
| Risk boundary at exactly 0.50 is alerted | `risk≈0.50` → alert | S06 |
| Mitigation text shape (both directions) | Reduce/Increase strings match the template | S07 |
| Unknown building rejected, no rows written | 400 `missingInputs=["building"]`, 0 rows | S08 |
| No prior `setpoint_recommendations` for building | 400 `missingInputs=["plan"]`, 0 rows | S09 |
| Partial plan coverage — skip uncovered zones | `decision` reflects only covered zones, the uncovered zone produces no row | S10 |
| Missing constraints on one zone → skip; on all zones → 400 | partial: zone skipped; collapse: 400 `missingInputs=["comfort_constraints"]` | S11 |
| Missing device state on one zone → skip | the zone produces no row | S12 |
| Cross-building isolation | run on A leaves B's tables intact | S13 |
| Atomicity — DB error mid-write | 0 new rows on 500 | S14 |
| Performance budget | `elapsed_ms < 3000` for 5-zone building | S15 |
| Determinism | two runs produce equal `risk_score`, `direction`, `mitigation` | S16 |
| UI flow | `/comfort-risk` page renders decision pill, alert rows, pass message | S17 |

## C) Acceptance Oracles

- **Decision oracle:** API `decision ∈ {'alert','pass'}` matches the materiality rule (A1) over the projected temperatures of every evaluable zone.
- **Persistence oracle (run):** Exactly one `comfort_risk_runs` row per 200 response, with the same `decision`, `alerts_count`, and `source_run_timestamp` as the API result.
- **Persistence oracle (alerts):** Exactly N `comfort_risk_alerts` rows where N = number of at-risk zones; each row carries `projected_temp_f`, `occupied_min_f`, `occupied_max_f`, `risk_score`, `direction`, `mitigation`. Skipped zones generate zero rows.
- **Mitigation oracle:** For an above-band alert with projected `P` and max `M`, the persisted mitigation equals `"Reduce setpoint by {round_half(P − M, 0.5)}°F to return to comfort band."`. Below-band uses Increase with `min − projected`.
- **Atomicity oracle (validation failure):** On 400, the `comfort_risk_runs` and `comfort_risk_alerts` row counts for the target building are unchanged.
- **Atomicity oracle (DB error):** On 500 due to forced mid-write failure, both row counts are unchanged.
- **Cross-building oracle:** Building B's row counts are unchanged after a run for A (S13).
- **Performance oracle:** Server `elapsed_ms` and client wall-clock both `< 3000 ms` for a 5-zone alert run (S15).
- **Determinism oracle:** Across two runs with identical fixtures, the multiset of `(zone_id, risk_score, direction, mitigation)` triples is equal (S16).
- **UI oracle:** `/comfort-risk` renders `comfort-risk-success-banner` on 200; `comfort-risk-decision-pill` reads `alert` or `pass`; one `comfort-risk-alert-row-{zone_id}` per alert with matching `-score-` and `-mitigation-` cells; `comfort-risk-pass-message` shown when `decision='pass'`.

## D) Deferred Scope (Recap)

- Real cron / background trigger for the Scheduler (A5).
- LLM-generated mitigations (A4).
- Real notification channel — pass path today is a stdlib INFO log (A8).
- Idempotency keys on detection runs (A9).
- Soft-fail on a zero-width comfort band (defensive skip today; not in scenarios).
