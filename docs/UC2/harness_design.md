# UC2: ImportOccupancySchedule — Service, Harness, and Traceability Design

## Part C) Service/Control Design Summary

### Application Service
Extend `BuildingService` (per service-to-use-case mapping: UC1 + UC2 both use `BuildingService`).

New methods:
- `list_buildings_with_zones() → list[BuildingSummary]` — returns buildings with their zones for the selector dropdown
- `import_occupancy_schedule(building_id: int, csv_content: str) → ImportResult` — parses CSV, validates rows atomically, persists on full success, raises `ImportFailure(errors)` on any row/header/empty error

### New Repository
`OccupancyRepository.save_all(records: list[OccupancyRecordInput])` — bulk insert; transactional

### External Dependencies
None

### Test Doubles
Not required for UC2 (all logic in-process)

---

## Part D) Acceptance Harness Design

### Before Each Scenario
- Reset 5 tables in FK order (`occupancy_records`, `operating_schedules`, `devices`, `zones`, `buildings`)
- Seed one building "HQ-East" with zones "Floor-1" and "Floor-2" (each with one dummy HVAC device)
- Store zone name → zone_id mapping in `context.zones` for step defs to generate CSV content with real zone IDs

### Simulated Actions
- Navigate to `/import-occupancy`
- Select a building from the dropdown
- Attach a CSV file (generated from Gherkin data table, raw docstring, empty file, or a 1000-row generated dataset)
- Click Submit

### Assertions
- **UI** — form elements visible; confirmation panel with numeric record count on success; row-error element with text containing the row number and field name; header-error element on header/empty failures
- **DB** — exact record count in `occupancy_records`; FK values point only to zones in the selected building; specific `(zone_id, timestamp, occupancy_count)` tuples present on success
- **Performance** — record `importTimeMs` from submit-click to confirmation-visible
- **Integrity** — zero rows in `occupancy_records` on any validation failure

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service/control elements |
|---|---|---|---|
| UC2-S01 | selector, file input, submit, confirmation | `occupancy_records` rows written, FK to seeded zones | `BuildingService.list_buildings_with_zones`, `BuildingService.import_occupancy_schedule`, `OccupancyRepository.save_all` |
| UC2-S02 | file input, row-error element | no rows written | `BuildingService.import_occupancy_schedule` (zone validation) |
| UC2-S03 | file input, row-error element | no rows written | `BuildingService.import_occupancy_schedule` (timestamp parse) |
| UC2-S04 | file input, row-error element | no rows written | `BuildingService.import_occupancy_schedule` (count parse) |
| UC2-S05 | file input, header-error element | no rows written | `BuildingService.import_occupancy_schedule` (header check) |
| UC2-S06 | file input, header-error element | no rows written | `BuildingService.import_occupancy_schedule` (empty check) |
| UC2-S07 | file input, confirmation | 1000 rows written; `importTimeMs` recorded | `BuildingService.import_occupancy_schedule` (timed) |
