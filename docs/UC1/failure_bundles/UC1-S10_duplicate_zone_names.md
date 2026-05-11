# UC1-S10 Failure Bundle — Duplicate Zone Names Not Rejected

## Input

- **Use case:** UC1 RegisterBuildingProfile
- **Failing scenario:** UC1-S10 Duplicate zone names within the same building show field error
- **Expected result:** Validation error for field `zones` is displayed; no building saved
- **Actual result:** Submit succeeded; both zones were persisted under the same building. No `error-zones` element ever rendered in the UI.
- **UI symptom:** Confirmation panel appeared instead of an inline `zones` error. Playwright timed out after 5s waiting for `[data-testid="error-zones"]`.
- **Database state:** A `buildings` row was written along with two `zones` rows sharing the same name and `building_id`, breaking the "no building is saved" half of the oracle.
- **Logs / stack trace:**
  ```
  playwright._impl._errors.TimeoutError: Page.wait_for_selector: Timeout 5000ms exceeded.
  Call log:
    waiting for locator("[data-testid=\"error-zones\"]") to be visible
  ```
- **Relevant code:**
  - `backend/app/services/building_service.py` — `BuildingService._validate` (the only place that builds the `errors` dict for field-shaped 400 responses)
  - `backend/app/domain/building.py` — `BuildingProfileInput.zones`
  - `frontend/src/pages/BuildingProfilePage/index.tsx` — already renders `error-zones` whenever `errors.zones` is present, so no UI change is needed.

---

## A) Failure Summary

- Scenario S10 expects two zones with the same `name` under the same building to be rejected at validation time with a field-keyed error under `zones`.
- `BuildingService._validate` currently only checks that `zones` is non-empty and that every zone has at least one device; it never compares zone names to one another.
- Because validation passes, the repository persists both rows, the API returns 201, the UI renders the confirmation panel, and Playwright never sees `error-zones`.

## B) Root Cause Hypothesis

`BuildingService._validate` is missing a uniqueness check across `profile.zones[*].name` within a single submission. There is no DB-level unique constraint on `(building_id, zone_name)` either, but the contract requires the service to reject this case before any write. A pure service-layer check keeps the integrity oracle intact (zero rows written on rejection) and matches the error-key convention used by S03 (`zones`).

## C) Candidate Fix Options

### Option 1 — Add a duplicate-name check to `_validate` (recommended)
Add a small block in `BuildingService._validate`, after the "zones must contain at least one zone" check, that collects normalised zone names (`zone.name.strip().lower()` or as-is per project convention) and sets `errors["zones"]` if duplicates are present. No DB changes, no schema changes.

- **Pros:** matches the existing validation pattern; one error key per offending field; no migration needed; same error shape S03 already produces; consistent integrity guarantee (zero rows written, since `_validate` runs before `repository.save`).
- **Cons:** does not enforce uniqueness at the DB level — a parallel session could theoretically still insert duplicates. Acceptable for UC1 (single FacilityManager workflow).
- **Risk:** very low. Only affects new validation paths.

### Option 2 — Add a DB-level unique constraint on `(building_id, name)` in `zones`
Create an Alembic migration adding `UniqueConstraint("building_id", "name")` on `zones`, and translate the `IntegrityError` into a `ValidationFailure` with key `zones` in the service.

- **Pros:** defence in depth — prevents duplicates even from non-UC1 code paths.
- **Cons:** adds a migration; the service still has to translate the `IntegrityError` after a failed `commit()` (or pre-check); ordering becomes awkward because the unique violation is detected only after the building row is inserted, which complicates the "no building is saved" half of the oracle (would need a transaction rollback). More moving parts for a UC1-scoped fix.
- **Risk:** medium — migrations + error translation are easy to get subtly wrong.

### Option 3 — Validate on the frontend before submit
Block `addZone` (or `handleSubmit`) when the entered name already exists in the zones-list state. Show inline UI error.

- **Pros:** instant feedback in the UI.
- **Cons:** acceptance harness drives the UI but the contract oracle is keyed off the backend error — duplicating the rule in two places risks drift; the backend would still accept a duplicate if reached directly. Acceptance test specifically asserts via the `error-{field}` selector after submit, which is rendered from the backend response.
- **Risk:** low, but solves the wrong layer.

### Recommendation

**Option 1.** It matches the prevailing validation idiom in `BuildingService`, requires no migration, and keeps the error-shape contract identical to the working S03 case.

## D) Verification Notes

Re-run after patch:
- **UC1-S10** — directly covers the failing behaviour; must produce `error-zones` and zero rows written.
- **UC1-S01, S06, S07** — confirm the happy paths still save (S06 in particular has three distinct zone names; the new check must not false-positive on that).
- **UC1-S03** — confirms the existing `zones` empty-list rule still fires.
- Full UC1 regression — confirm no scenario flips.

Expected post-patch result: 17/17 scenarios pass.
