# UC1-S02 Failure Bundle — Pydantic 422 vs Service 400 Error Shape Mismatch

## Input

- **Use case:** UC1 RegisterBuildingProfile
- **Failing scenario:** UC1-S02 Missing building name shows specific field error
- **Expected result:** Validation error for field "buildingName" is displayed; no building saved
- **Actual result:** No `error-buildingName` element ever rendered in the UI; Playwright timed out after 5s waiting for the selector
- **UI symptom:** Submit button pressed, no inline error appeared, confirmation panel also absent
- **Database state:** `buildings` table remained empty (so the "no save" half of the oracle passed)
- **Logs / stack trace:**
  ```
  playwright._impl._errors.TimeoutError: Page.wait_for_selector: Timeout 5000ms exceeded.
  Call log:
    waiting for locator("[data-testid=\"error-buildingName\"]") to be visible
  ```
- **Relevant code:**
  - `backend/app/domain/building.py` — `BuildingProfileInput.building_name`
  - `backend/app/services/building_service.py` — `BuildingService._validate`
  - `backend/app/api/routes/building.py` — exception handling for `ValidationFailure`
  - `frontend/src/services/api.ts` — `registerBuildingProfile` response handling

---

## A) Failure Summary

- Scenario UC1-S02 expected the UI to render `error-buildingName` after submitting an empty building name
- The backend returned HTTP 422 (Pydantic's native validation error) instead of HTTP 400 (the service-layer `ValidationFailure` shape)
- The frontend's response handler only mapped 400 responses to field-keyed errors; 422 fell through to the generic "Unexpected error" path and never populated `errors.buildingName`
- Integrity half of the oracle passed (no rows written); UI half failed

## B) Root Cause Hypothesis

Two validation layers were both trying to reject the empty building name:

1. **Pydantic schema** — `building_name: str = Field(..., min_length=1)` rejected `""` at the FastAPI request-parsing stage, returning Pydantic's 422 format before the service was invoked
2. **Service-level `_validate`** — would have produced the expected 400 response with `{detail: {errors: {buildingName: "..."}}}`, but it never ran because Pydantic failed first

The frontend only handles the 400 shape. Pydantic's 422 bypassed the service, so the contract-shaped error never reached the UI.

## C) Minimal Patch Plan

1. Remove `Field(..., min_length=1)` constraints from `BuildingProfileInput`, `ZoneInput`, `DeviceInput`, and `OperatingScheduleInput` in `backend/app/domain/building.py`
2. Default each such string field to `""` so Pydantic accepts empty values at the parse stage
3. Leave the service-level `_validate` unchanged — it already detects empty/whitespace-only values and names the specific field
4. No changes to frontend, repository, or route layer

This makes `BuildingService._validate` the single source of truth for field-presence validation, producing a consistent 400 error shape.

## D) Verification Notes

Re-run after patch:
- **UC1-S02** — directly covers the failing behavior; must return `error-buildingName`
- **UC1-S03** — confirms the `zones` field-presence check still works via the service
- **UC1-S04** — confirms the schedule-time validation still works via the service
- **UC1-S01** — confirms the happy path still saves correctly (no regression on successful submit)
- **UC1-S05** — confirms performance is unaffected by removing schema constraints

Post-patch result: **5 scenarios passed, 0 failed, 47 steps passed**.
