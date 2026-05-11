# UC1: RegisterBuildingProfile — Structured Requirement

## A) Structured Requirement

**Use case:** RegisterBuildingProfile

**Actors:** FacilityManager (initiator), Building Repository

**Goal:** Create and persist a validated building profile containing zones, devices, and operating schedules.

### Preconditions
- FacilityManager is authenticated

### Main Success Flow
1. FacilityManager activates Register Building Profile
2. System presents form for building name, zones, devices, operating schedules
3. FacilityManager fills in fields and submits
4. System validates all required fields
5. System persists the profile in the Building Repository
6. System displays a confirmation with the new building ID

### Success Postconditions
- Validated building profile persisted in Building Repository
- Confirmation visible to FacilityManager

### Failure Postconditions
- No profile saved
- Field-level error messages visible identifying each invalid field
- User remains on the form with entered values preserved

### Quality Requirements
- `saveTimeMs < 4000`
- Validation is deterministic and identifies the specific missing/invalid field

### Assumptions
- **A1:** Required fields are: `buildingName`, at least one `zone` (with `zoneName`), at least one `device` per zone (with `deviceType`), and at least one `operatingSchedule` entry.
- **A2:** `saveTimeMs` is measured end-to-end from submit click to confirmation rendering.
- **A3:** Authentication is handled by existing auth context; UC1 assumes an authenticated session exists.
- **A4:** Schedule validation checks that `startTime < endTime` and hours are within 00:00–23:59.

---

## B) Acceptance Checks Table

| Use-case statement | Acceptance check |
|---|---|
| FacilityManager activates function | UI exposes a Register Building Profile entry point |
| System presents form | Form with zones, devices, schedules is visible |
| FacilityManager submits | Submit action captures all entered values |
| System validates | Field-level validation errors visible for invalid inputs |
| System stores profile | Building row persisted in DB with zones/devices/schedules |
| System confirms | Confirmation visible with building ID |
| Save within 4s | `saveTimeMs < 4000` |
| Specific field errors | Each error message names the exact field |
| Multiple zones per building | Each zone persists with its own deviceType |
| Multiple schedules per building | Each schedule row persists independently |
| Missing deviceType | Field-level error names `deviceType` |
| Missing schedule | Field-level error names `operatingSchedule` |
| Duplicate zone names in one building | Field-level error names `zones` |
| Long building name (100 chars) | Name persisted without truncation |
| Multiple invalid fields on one submit | All offending fields reported in the same response |
| Form state after validation failure | Entered values remain visible to user |
| Duplicate building names across submissions | Both persisted with distinct IDs |
| Whitespace-only building name | Treated as missing; field-level error names `buildingName` |
| Equal start/end schedule times | Field-level error names `operatingSchedule` |
| Confirmation ID consistency | Returned building ID equals the persisted record's ID |

---

## C) Acceptance Oracles

- **UI oracle:** Register Building Profile form visible with all required inputs
- **Form oracle:** Submit triggers an API call with captured form values
- **Persistence oracle:** Building + Zone + Device + Schedule rows exist in DB after success
- **Validation oracle:** Each field-level error names the specific field
- **Confirmation oracle:** Success message with building ID visible
- **Performance oracle:** `saveTimeMs < 4000`
- **Integrity oracle:** No DB writes occur on validation failure
- **Multi-zone oracle (S06):** Repository returns N zones for the building, each with the deviceType originally submitted
- **Multi-schedule oracle (S07):** Repository returns N schedule entries for the building, all present
- **Missing-device oracle (S08):** Validation response identifies `deviceType` as the offending field
- **Missing-schedule oracle (S09):** Validation response identifies `operatingSchedule` as the offending field
- **Duplicate-zone oracle (S10):** Validation response identifies `zones` and no record is saved
- **Long-name oracle (S11):** Saved `buildingName` length equals 100; characters preserved byte-for-byte
- **Multi-error oracle (S12):** Single submit response lists `buildingName`, `zones`, and `operatingSchedule` errors simultaneously
- **State-preservation oracle (S13):** After failed submit, UI inputs still reflect the previously entered values
- **Duplicate-building-name oracle (S14):** Two persisted records share the name and have distinct primary-key IDs
- **Whitespace-name oracle (S15):** Validation response identifies `buildingName` when input is only spaces
- **Equal-time oracle (S16):** Validation response identifies `operatingSchedule` when `startTime == endTime`
- **ID-consistency oracle (S17):** ID returned in the confirmation UI equals the ID stored in the repository for that building
