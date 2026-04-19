# UC2: ImportOccupancySchedule — Structured Requirement

## A) Structured Requirement

**Use case:** ImportOccupancySchedule

**Actors:** FacilityManager (initiator), Building Repository

**Goal:** Parse and persist an occupancy schedule (list of `(zone_id, timestamp, occupancy_count)` records) for an existing building, linking each record to a zone.

### Preconditions
- FacilityManager is authenticated
- At least one building profile exists with at least one zone

### Main Success Flow
1. FacilityManager activates Import Occupancy Schedule
2. System presents form with building selector + CSV file upload
3. FacilityManager selects a building and uploads a CSV
4. System validates CSV header and parses each row
5. System verifies each `zone_id` belongs to the selected building
6. System persists all records atomically
7. System displays confirmation with imported record count

### Success Postconditions
- All rows persisted, each linked by FK to a zone of the selected building
- Confirmation shows record count

### Failure Postconditions
- No records saved (atomic)
- Error message identifies the specific row and offending field (or a header-level / empty-file issue)

### Quality Requirements
- `importTimeMs < 5000` for a 1000-row dataset
- Parsing errors name the exact row number (header = row 1) and the offending field

### Assumptions
- **A1:** CSV header is exactly `zone_id,timestamp,occupancy_count`
- **A2:** Timestamp format is ISO 8601 (`YYYY-MM-DDTHH:MM:SS`)
- **A3:** `occupancy_count` must be a non-negative integer
- **A4:** `zone_id` must reference a zone belonging to the selected building; otherwise the row is rejected
- **A5:** Manual data entry is **out of scope** for UC2 — CSV upload satisfies the OR clause in the UC spec. Manual entry may be added in a later iteration.
- **A6:** Import is all-or-nothing: any invalid row aborts the whole import
- **A7:** "Seeded dataset" = 1000 rows for the performance oracle

---

## B) Acceptance Checks Table

| Use-case statement | Acceptance check |
|---|---|
| FM activates import function | UI exposes Import Occupancy Schedule entry |
| System presents options | Building selector + file upload visible |
| FM uploads CSV | File attached to submit |
| System parses and validates | Valid rows produce persisted records |
| System links to zones | Each record FK → zone within selected building |
| System stores schedule | Rows persist in `occupancy_schedule` table |
| System confirms import | Confirmation panel with record count |
| Parsing errors identify row | Error names row number and field |
| Import within 5s | `importTimeMs < 5000` for 1000 rows |
| No-save on error | Zero rows written if any row invalid |

---

## C) Acceptance Oracles

- **UI oracle:** Import form visible with building selector and file input
- **Upload oracle:** Submit triggers API call carrying the file and selected building
- **Persistence oracle:** Rows in `occupancy_schedule` table with correct zone FKs (on success)
- **Row-error oracle:** Error message names specific row number and offending field
- **Header-error oracle:** Error message names the header issue when columns are wrong
- **Empty-file oracle:** Error message indicates empty input
- **Confirmation oracle:** Success panel with numeric record count
- **Performance oracle:** `importTimeMs < 5000` for 1000-row import
- **Integrity oracle:** No rows written when any validation fails
