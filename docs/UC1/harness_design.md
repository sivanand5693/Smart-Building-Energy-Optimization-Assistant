# UC1: RegisterBuildingProfile — Service, Harness, and Traceability Design

## Part C) Service/Control Design Summary

### Application Service
- **`BuildingService`**
  - `registerBuildingProfile(profile: BuildingProfileInput) → BuildingProfileResult`
  - Performs validation, then delegates to `BuildingRepository` for persistence

### External Dependencies
- None for UC1 (no AI/ML, no device control, no external services)

### Test Doubles
- Not required for UC1 — all logic is in-process against the real test database

---

## Part D) Acceptance Harness Design

### Before Each Scenario
- Reset all 4 tables in FK order (`operating_schedules`, `devices`, `zones`, `buildings`)
- Stub the session as authenticated (authenticated FacilityManager context)

### Simulated Actions
- Navigate to `RegisterBuildingProfilePage`
- Fill `buildingName`
- Add one or more zones, each with one or more devices
- Add one or more operating schedules
- Click Submit

### Assertions
- **UI** — form rendered; confirmation panel visible on success; inline field errors visible on validation failure with error text containing the specific field name
- **DB** — on success: exact row counts and field values across `buildings`, `zones`, `devices`, `operating_schedules`. On failure: zero rows written to any of the 4 tables
- **Performance** — record `saveTimeMs` from submit click to confirmation visible
- **Integrity** — no rows written when validation fails

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service/control elements |
|---|---|---|---|
| UC1-S01 | form inputs, confirmation panel | `buildings`, `zones`, `devices`, `operating_schedules` | `BuildingService.registerBuildingProfile`, `BuildingRepository.save` |
| UC1-S02 | form inputs, `buildingName` error | no rows written | `BuildingService.validate` |
| UC1-S03 | form inputs, `zones` error | no rows written | `BuildingService.validate` |
| UC1-S04 | form inputs, `operatingSchedule` error | no rows written | `BuildingService.validate` |
| UC1-S05 | form inputs, confirmation panel | all 4 tables written | `BuildingService.registerBuildingProfile` (timed) |
