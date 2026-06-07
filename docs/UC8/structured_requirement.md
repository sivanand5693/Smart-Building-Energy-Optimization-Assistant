# UC8 ExplainRecommendation — Structured Requirement

## A) Structured Requirement

**Use case name:** ExplainRecommendation

**Participating actors:**
- FacilityManager (primary; selects a recommendation and activates the "Explain Recommendation" function).
- ExplanationService (control).
- ExplanationAdapter (new external boundary; deterministic test double for acceptance, production binding deferred to a real Claude API wiring).
- SetpointRecommendationStore (DB-backed; `setpoint_recommendations` table — read-only context).
- ZoneComfortConstraintStore (DB-backed; `zone_comfort_constraints` table — read-only context).
- OccupancyRecordStore (DB-backed; `occupancy_records` table — read-only context).
- DemandForecastStore (DB-backed; `demand_forecasts` table — read-only context).
- RecommendationExplanationStore (DB-backed; **new** `recommendation_explanations` table — write; UNIQUE per `recommendation_id` for idempotency).

**Goal:** When the FacilityManager activates the "Explain Recommendation" function for an existing recommendation, the system retrieves the inputs (latest occupancy snapshot for the zone, latest demand forecast for the zone, comfort constraints for the zone) and projected outcomes (`projected_savings_kwh`, `comfort_impact`, `setpoint_delta_f`) associated with the recommendation; identifies the dominant **energy**, **comfort**, and **occupancy** factors; calls the `ExplanationAdapter.explain(...)` boundary to produce a concise natural-language string plus a structured `factors_json` payload that explicitly names each of the three factor buckets; persists one row in `recommendation_explanations` (UNIQUE by `recommendation_id`); and returns the explanation result to the caller. On a repeat call for the same recommendation the persisted row is returned without re-invoking the adapter (`cached=true`).

**Preconditions:**
- A recommendation row exists in `setpoint_recommendations` (UC4) for the recommendation_id being explained.
- For that recommendation's zone, **all** of the following are available:
  - a `zone_comfort_constraints` row,
  - at least one `occupancy_records` row at-or-before the recommendation's `run_timestamp`,
  - a `demand_forecasts` row for the zone whose `timestamp == run_timestamp`.
- The ExplanationAdapter is wired (production stub raises `NotImplementedError`; acceptance double is wired under `TESTING=1`).

**Trigger boundary:** `POST /api/recommendations/{recommendation_id}/explain` (no body).

**Main success flow:**
1. The FacilityManager (or any caller) POSTs the explain endpoint for the target recommendation.
2. The system loads the `setpoint_recommendations` row. Missing → 400 `missingInputs=["recommendation"]`.
3. The system loads, for the recommendation's zone, the `zone_comfort_constraints` row, the latest `occupancy_records` row at-or-before `run_timestamp`, and the `demand_forecasts` row for `(zone_id, run_timestamp)`. Any subset that is missing is accumulated into `missingInputs` (sorted alphabetically) → 400 with the full list; no row is written.
4. The system checks for an existing `recommendation_explanations` row keyed by `recommendation_id`. If present → return it (`cached=true`, `elapsed_ms` measures only the cache lookup); the adapter is **not** invoked.
5. Otherwise the system assembles an `ExplanationInputs` payload (recommendation fields + the three context rows) and calls `ExplanationAdapter.explain(recommendation_id, inputs)`. The adapter returns `(text, factors, model_version)`.
6. The system writes a single `recommendation_explanations` row inside one SQLAlchemy transaction with `recommendation_id`, `text`, `factors_json`, `elapsed_ms` (server-measured), `model_version`. Commit.
7. Return `ExplanationResult` carrying `recommendation_id`, `text`, `factors`, `cached=false`, `elapsed_ms`, `model_version`, `generated_at`.

**Success postconditions:**
- Exactly one `recommendation_explanations` row exists for `recommendation_id` after the first 200 response.
- Re-calling the endpoint produces a 200 with `cached=true` and identical `text` / `factors`; row count remains 1.
- `GET /api/recommendations/{recommendation_id}/explanation` returns the cached row when present, otherwise 404.

**Failure postconditions:**
- On any `missingInputs` 400: zero new `recommendation_explanations` rows.
- On a mid-write DB error: transaction rolls back; row count unchanged; API returns 500.

**Quality requirements:**
- Q1: Explanation text references all three factor buckets — the case-insensitive substrings `energy`, `comfort`, and `occupancy` are all present, plus the numeric `projected_savings_kwh`, the `comfort_impact` enum word (`none`/`minor`/`moderate`), and the latest occupancy count value (A5; S01, S11).
- Q2: First-generation latency `elapsed_ms < 4000` (A6; S12).
- Q3: Cached-response latency `elapsed_ms < 500` (A6; S13).
- Q4: Persistence is atomic per request (A7; S14).
- Q5: Determinism — for identical inputs, two distinct recommendations produce identical `text` (modulo the recommendation_id field that is intentionally not part of the body string) (A1; S04).

### Numbered Assumptions

- **A1** Explanation = `ExplanationAdapter.explain(recommendation_id, inputs)` returns `(text, factors, model_version)` deterministically. Real Claude API wiring is **deferred**; production binding raises `NotImplementedError`.
- **A2** "Dominant factors" maps to exactly three buckets: **energy** (`projected_savings_kwh`), **comfort** (`comfort_impact` enum value), **occupancy** (latest `occupancy_records.occupancy_count` for the zone at-or-before the recommendation's `run_timestamp`). All three appear in the explanation text — Q1 oracle.
- **A3** Idempotency: `recommendation_explanations.recommendation_id` carries a UNIQUE constraint. A repeated POST returns the cached row (no adapter re-invocation), `cached=true`, identical `text` / `factors`.
- **A4** Insufficient-context exit path: if any of {recommendation, comfort_constraints, occupancy_records, demand_forecasts} for the recommendation/zone is missing, the API returns 400 with `missingInputs=[...]` (sorted alphabetically); no row is written.
- **A5** Quality Q1 oracle — the explanation text contains case-insensitive substrings `energy`, `comfort`, `occupancy`, the numeric `projected_savings_kwh` (formatted to three decimals to match the DB column), the `comfort_impact` enum word, and the integer `occupancy_count`.
- **A6** Quality Q2/Q3 — first-generation `elapsed_ms < 4000`; cached `elapsed_ms < 500`.
- **A7** Atomic single-transaction commit per request. On any mid-write exception the transaction rolls back and zero new rows survive (S14).
- **A8** No background generation; trigger = the POST. There is no scheduled or cron-driven path.
- **A9** `model_version` string is returned by the adapter and recorded on the row. The double returns `"explanation-double-v1"`; production binding deferred per A1.
- **A10** `factors_json` is a JSON object with exactly the keys `energy`, `comfort`, `occupancy`; each value is a short string carrying the underlying value (e.g. `{"energy": "1.500 kWh", "comfort": "minor", "occupancy": "12 occupants"}`). Schema is enforced by the double; production adapter is contractually bound to the same shape.
- **A11** The `cached` flag is **derived at request time** (UC8 service decides) and is **not** persisted on the row. The persisted row is identical whether read for the first or hundredth time.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| Happy path explanation references all three factors | 200 + text contains case-insensitive `energy`/`comfort`/`occupancy` + numeric savings | S01 |
| `factors_json` shape | 200 body `factors_json` has keys `energy`, `comfort`, `occupancy`, each non-empty | S02 |
| Idempotency — second call is cached, adapter not re-invoked | 200 with `cached=true`, DB row count == 1, adapter invocation count == 1 | S03 |
| Determinism across different recommendations with identical inputs | text fields equal modulo recommendation_id-bound substrings | S04 |
| Unknown recommendation_id | 400 `missingInputs=["recommendation"]` | S05 |
| Missing comfort constraints for the zone | 400 `missingInputs=["comfort_constraints"]` | S06 |
| Missing occupancy records for the zone | 400 `missingInputs=["occupancy"]` | S07 |
| Missing forecast row for the zone | 400 `missingInputs=["forecast"]` | S08 |
| Multiple missing inputs accumulate, sorted alphabetically | 400 `missingInputs=["comfort_constraints","occupancy"]` | S09 |
| Cross-building isolation — explain on A doesn't touch B | DB row only exists for A's recommendation, B count == 0 | S10 |
| Quality Q1 — text mentions `comfort_impact` word and occupancy count | text contains both substrings verbatim | S11 |
| Quality Q2 — first-generation `elapsed_ms < 4000` | 200 + body.elapsed_ms < 4000 | S12 |
| Cached response is fast — `elapsed_ms < 500` | second 200 + body.elapsed_ms < 500 | S13 |
| Atomicity — DB error mid-write rolls back | 500 + 0 new rows | S14 |
| Model version persisted and surfaced | row.model_version == `"explanation-double-v1"`; API body matches | S15 |
| GET endpoint returns cached row, 404 otherwise | GET 200 after POST; GET 404 before POST | S16 |
| UI flow via `/explain` | Playwright sees explain-text + three factor sections + cached pill + model-version pill | S17 |

## C) Acceptance Oracles

- **Persistence oracle:** Exactly one `recommendation_explanations` row per `recommendation_id` after a successful explain; the row carries `text`, `factors_json` (`energy`/`comfort`/`occupancy`), `elapsed_ms`, `model_version`.
- **Idempotency oracle (DB):** The row count for `recommendation_id` stays at 1 across N successful POSTs (S03).
- **Idempotency oracle (adapter):** The double's invocation counter increments exactly once across N successful POSTs for the same `recommendation_id` (S03).
- **Determinism oracle:** Two recommendations with identical input fixtures produce explanation `text` strings whose recommendation_id-independent portions are equal (S04).
- **Missing-inputs oracle:** 400 response carries `detail.missingInputs` as a list whose entries are drawn from the closed set `{recommendation, comfort_constraints, occupancy, forecast}`, sorted alphabetically; the table row count for the target `recommendation_id` is unchanged (S05–S09).
- **Atomicity oracle:** On a forced 500 mid-write, the `recommendation_explanations` row count for the target `recommendation_id` is unchanged (S14).
- **Cross-building oracle:** A POST against building A's recommendation does not create any row for any of building B's recommendations (S10).
- **Quality oracle Q1 (text shape):** The `text` field contains case-insensitive `energy`, `comfort`, `occupancy` substrings, the formatted `projected_savings_kwh` (three decimals), the `comfort_impact` enum word, and the integer `occupancy_count` (S01, S11).
- **Quality oracle Q2 (perf):** First-generation `elapsed_ms < 4000` (S12).
- **Quality oracle Q3 (cache perf):** Cached `elapsed_ms < 500` (S13).
- **GET oracle:** `GET /api/recommendations/{id}/explanation` returns 200 + row body when a row exists; 404 otherwise (S16).
- **UI oracle:** `/explain` page renders `explain-success-banner` on 200; `explain-text` displays the explanation; `explain-factor-energy` / `explain-factor-comfort` / `explain-factor-occupancy` render the three factor strings; on the second submit `explain-cached-pill` becomes visible; `explain-model-version` displays the adapter model version (S17).

## D) Deferred Scope (Recap)

- Real Claude API wiring for the `ExplanationAdapter` — production binding raises `NotImplementedError` (A1).
- Background or scheduled explanation generation — only the POST trigger exists (A8).
- Per-user authentication / authorization — the explain endpoint is invocable by any caller in the test harness.
- Multi-language explanations — English templated text only.
- Persisted `cached` flag — derived at request time, not stored (A11).
