# UC8 ExplainRecommendation — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`ExplanationService`** — `backend/app/services/explanation_service.py`

Public methods:
- `explain(recommendation_id: int) -> ExplanationResult`
- `get_existing(recommendation_id: int) -> ExplanationResult | None`

`explain` steps (single SQLAlchemy session, single commit at the end):
1. Load the `SetpointRecommendationModel` row by `recommendation_id`. Missing → raise `ExplanationInputsMissing(["recommendation"])`.
2. Resolve `zone_id` and `run_timestamp` from the recommendation row.
3. Probe each of the three context inputs and accumulate missing labels (sorted alphabetically):
   - `comfort_constraints` ← `ZoneComfortConstraintRepository.for_zone(zone_id)`.
   - `occupancy` ← `OccupancyRepository.latest_for_zone_at_or_before(zone_id, run_timestamp)`.
   - `forecast` ← `DemandForecastRepository.for_zone_at(zone_id, run_timestamp)` (new helper that selects the row whose `timestamp == run_timestamp`).
   If any are missing → raise `ExplanationInputsMissing(sorted_labels)`.
4. Cache check: `ExplanationRepository.get_for_recommendation(recommendation_id)`. If present → return a `ExplanationResult(..., cached=True, elapsed_ms=<lookup-time>)` and **do not** invoke the adapter.
5. Build `ExplanationInputs(recommendation_id, zone_id, zone_name, projected_savings_kwh, comfort_impact, setpoint_delta_f, occupancy_count, occupancy_timestamp, predicted_kwh, occupied_min_f, occupied_max_f)`.
6. Call `ExplanationAdapter.explain(recommendation_id, inputs)` → `(text, factors, model_version)`.
7. If `_force_db_error_flag` is set (test lever), raise `ExplanationForcedDbError` so the route maps to 500 and the transaction rolls back.
8. Persist via `ExplanationRepository.save_no_commit(RecommendationExplanationModel(...))`, then `db.commit()`.
9. Return `ExplanationResult(recommendation_id, text, factors, cached=False, elapsed_ms=<server-measured>, model_version, generated_at)`.

Atomicity: any exception inside the try block → `db.rollback()` + re-raise.

### Domain types — `backend/app/domain/explanation.py`
- `ExplanationInputs` (dataclass): `recommendation_id`, `zone_id`, `zone_name`, `projected_savings_kwh: Decimal`, `comfort_impact: str`, `setpoint_delta_f: Decimal`, `occupancy_count: int`, `occupancy_timestamp: datetime`, `predicted_kwh: Decimal`, `occupied_min_f: Decimal`, `occupied_max_f: Decimal`.
- `ExplanationResult` (dataclass): `recommendation_id`, `text`, `factors: dict[str, str]`, `cached: bool`, `elapsed_ms: float`, `model_version: str`, `generated_at: datetime | None`.
- `ExplanationInputsMissing(Exception)` with `missing_inputs: list[str]`.
- `ExplanationForcedDbError(Exception)` — test lever.

### Repositories
**`ExplanationRepository`** — `backend/app/infrastructure/repositories/explanation_repository.py`
- `save_no_commit(row: RecommendationExplanationModel) -> None` — add + flush, caller commits.
- `get_for_recommendation(recommendation_id: int) -> RecommendationExplanationModel | None`.
- `count_for_recommendation(recommendation_id: int) -> int`.

**`DemandForecastRepository`** (extended)
- `for_zone_at(zone_id: int, ts: datetime) -> DemandForecastModel | None` — exact `timestamp == ts` match.

### Adapter
**`ExplanationAdapter` Protocol** — `backend/app/infrastructure/adapters/explanation_adapter.py`.
Method: `explain(recommendation_id: int, inputs: ExplanationInputs) -> tuple[str, dict[str, str], str]` returning `(text, factors, model_version)`.

**Production stub** — same file. Class `_NotWiredExplanation` raises `NotImplementedError("real ExplanationAdapter not wired (UC8 deferred)")`.

**Acceptance double** — `tests/acceptance/support/test_doubles/explanation_adapter_double.py`. Class `ExplanationAdapterDouble`:
- Tracks an integer invocation counter (`calls_count`).
- `explain(...)` returns a deterministic templated string of the form:
  `"This recommendation projects energy savings of {savings:.3f} kWh with {impact} comfort impact for a zone currently showing {count} occupants in the latest occupancy snapshot."`
  (Contains case-insensitive `energy`, `comfort`, `occupancy` substrings, the formatted savings, the comfort_impact word, and the occupancy count.)
- `factors`: `{"energy": "{savings:.3f} kWh", "comfort": "{impact}", "occupancy": "{count} occupants"}`.
- `model_version`: `"explanation-double-v1"`.

`use_test_doubles()` swaps the registry's adapter to the double; the production binding is the no-wired stub.

### API routes — `backend/app/api/routes/explanations.py` (new; register in `main.py`)
- `POST /api/recommendations/{recommendation_id}/explain` → 200 `ExplanationResponse`, 400 `{detail:{missingInputs:[...]}}`, 500.
- `GET /api/recommendations/{recommendation_id}/explanation` → 200 `ExplanationResponse` | 404.

`ExplanationResponse` Pydantic model fields: `recommendation_id`, `text`, `factors` (object), `cached` (bool), `elapsed_ms` (float), `model_version`, `generated_at` (datetime, nullable).

### Wiring
`app.api.routes.explanations.router` mounted in `main.py`. Under `TESTING=1`, `app.infrastructure.adapters.explanation_adapter.use_test_doubles()` is called so the registry's adapter is the double.

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)
No change beyond extending the DB truncate (covered in `database_reset.py`).

### Test doubles
**New double:** `tests/acceptance/support/test_doubles/explanation_adapter_double.py` (see above).

Reuses: `WeatherAdapterDouble`, `DeviceStateAdapterDouble`, `ForecastModelDouble`, `OptimizationAdapterDouble`, `DeviceControlAdapterDouble` from UC1–UC7.

### Test-only control endpoints (added to `app/api/routes/test_support.py`)
- `POST /api/_test/explanation/reset` — resets the double's invocation counter.
- `GET  /api/_test/explanation/calls` → `{"calls": <int>}`. Used by S03.
- `POST /api/_test/explanation/force_db_error` — toggles the service-level flag so the next `explain()` call raises mid-write.

### Step definitions (`tests/acceptance/steps/UC8_steps.py`)
Reuses every UC1/UC3/UC4/UC7 background step. New UC8 steps:

| Step | Action |
|---|---|
| `Given the ExplanationAdapter test double is reset` | POST `/api/_test/explanation/reset`. |
| `Given the ExplanationService is configured to force a DB error on the next request` | POST `/api/_test/explanation/force_db_error`. |
| `Given all occupancy records for zone "<zone>" of "<bldg>" are deleted` | POST `/api/_test/clear_occupancy_for_zone`. |
| `When the FacilityManager requests an explanation for the latest recommendation of zone "<zone>" of "<bldg>"` | resolve `recommendation_id` via `GET /api/buildings/{id}/recommendations/latest`, then POST `/api/recommendations/{rid}/explain`. Stash response + elapsed. |
| `When the FacilityManager requests an explanation for recommendation id <id>` | POST `/api/recommendations/<id>/explain`. |
| `When the FacilityManager fetches the explanation for the latest recommendation of zone "<zone>" of "<bldg>"` | resolve id, GET `/api/recommendations/{rid}/explanation`. |
| `When the explanation text is captured as the baseline for zone "<zone>" of "<bldg>"` | stash `context.explain_baseline_text` + `context.explain_baseline_rid`. |
| `When the user requests an explanation for zone "<zone>" of "<bldg>" via the ExplainPage` / `again` | Playwright drive `/explain`. |
| `Then the explanation response status is <code>` | assert status. |
| `Then the explanation text contains case-insensitive substring "<s>"` | `s.lower() in body["text"].lower()`. |
| `Then the explanation text contains the projected_savings_kwh value` | resolve the recommendation row's formatted savings and assert it appears verbatim. |
| `Then the explanation text contains the comfort_impact value` | assert the recommendation's `comfort_impact` enum appears verbatim. |
| `Then the explanation text contains the latest occupancy_count value` | assert the occupancy count integer appears verbatim. |
| `Then the explanation factors object has a non-empty "<key>" entry` | `body["factors"][key]` non-empty. |
| `Then the explanation response has cached "<bool>"` | `body["cached"]` truthiness match. |
| `Then the explanation adapter has been invoked <n> time(s)` | GET `/api/_test/explanation/calls`. |
| `Then the database contains <n> recommendation_explanations row for the latest recommendation of zone "<zone>" of "<bldg>"` | SQL count via test engine. |
| `Then the explanation response missingInputs equals <list>` | `body["detail"]["missingInputs"] == <list>`. |
| `Then the explanation response elapsed_ms is under <ms>` | `body["elapsed_ms"] < ms`. |
| `Then the explanation response model_version equals "<v>"` | exact match. |
| `Then the persisted recommendation_explanations row model_version equals "<v>" for ...` | SQL probe. |
| `Then the explanation text for zone "X" of "B" matches the baseline for zone "Y" of "B" modulo identifiers` | compare text strings ignoring recommendation_id occurrences. (Double's text contains no recommendation_id, so plain equality holds.) |
| `Then the ExplainPage shows the success banner` / `explanation text` / `three factor sections` / `model-version pill` / `cached pill` | Playwright selector waits. |

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC8-S01 Happy path | n/a | 1 explanations row | adapter invoked once; text shape oracle |
| UC8-S02 Factors JSON shape | n/a | 1 row | `factors_json` keys non-empty |
| UC8-S03 Idempotency | n/a | 1 row across two POSTs | adapter `calls_count == 1`, `cached=true` on 2nd |
| UC8-S04 Determinism | n/a | 2 rows (different recs) | identical text modulo ids |
| UC8-S05 Unknown rec id | n/a | 0 rows | `ExplanationInputsMissing(["recommendation"])` |
| UC8-S06 Missing constraints | n/a | 0 rows | `["comfort_constraints"]` |
| UC8-S07 Missing occupancy | n/a | 0 rows | `["occupancy"]` |
| UC8-S08 Missing forecast | n/a | 0 rows | `["forecast"]` |
| UC8-S09 Multi-missing sorted | n/a | 0 rows | `["comfort_constraints","occupancy"]` |
| UC8-S10 Cross-building | n/a | 1 row for A, 0 for B | scoping by recommendation_id |
| UC8-S11 Q1 text shape | n/a | 1 row | text contains comfort word + occupancy count |
| UC8-S12 Perf Q2 | n/a | 1 row | `elapsed_ms < 4000` |
| UC8-S13 Cached perf | n/a | 1 row | `elapsed_ms < 500` on 2nd call |
| UC8-S14 Atomicity | n/a | 0 rows after 500 | service rollback + 500 |
| UC8-S15 Model version | n/a | 1 row | `model_version == "explanation-double-v1"` |
| UC8-S16 GET endpoint | n/a | 1 row after POST | 404 → 200 transition |
| UC8-S17 UI flow | banner, text, 3 factor cells, model pill, cached pill | 1 row | `/explain` page |
