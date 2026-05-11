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
| Zone scoping is per-building | A zone owned by another building is rejected as `zone_id` error |
| Non-negative occupancy | Negative `occupancy_count` rejected on the offending row |
| Strict `zone_id` typing | Non-integer `zone_id` rejected as `zone_id` error |
| Strict column count | Rows with wrong column count rejected with a row-level error (no field) |
| Atomic multi-error reporting | All invalid rows surfaced in one response when any row fails |
| Robust to blank lines | Empty data rows are skipped, surrounding valid rows persist |
| Whitespace-tolerant header | Header cells with leading/trailing spaces still match `EXPECTED_HEADER` |
| Submit gated by inputs | Submit button disabled until building selected AND file attached |
| Reject empty data | Header-only files rejected with a "no data rows" error |

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
- **Cross-building zone oracle:** A `zone_id` valid in another building is rejected with field `zone_id` for the selected building (S08)
- **Negative-count oracle:** `occupancy_count < 0` surfaces a row-level error with field `occupancy_count` (S09)
- **Non-integer zone_id oracle:** A non-numeric `zone_id` surfaces a row-level error with field `zone_id` (S10)
- **Column-count oracle:** A row with more/fewer than three columns surfaces a row-level error with no `field` (S11)
- **Multi-error oracle:** All offending rows are returned in a single response; none are persisted (S12)
- **Blank-line oracle:** All-empty CSV rows between data rows are silently skipped (S13)
- **Header-whitespace oracle:** Header cells like `"zone_id "` or `" timestamp"` are normalized via strip before matching `EXPECTED_HEADER` (S14)
- **Submit-gating oracle:** The submit button is disabled when either building or file is unset (S15)
- **Header-only oracle:** A file containing only the header row is rejected with a "no data rows" file-level error (S16)
