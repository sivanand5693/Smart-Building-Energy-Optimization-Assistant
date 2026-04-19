# UC2: ImportOccupancySchedule — UI Design

## Part A) UI Design Summary

### Main Page
`ImportOccupancySchedulePage` at route `/import-occupancy`

### Inputs
- **Building selector** — `<select>` populated from `GET /api/buildings`; displays building name, value is `building_id`
- **File input** — `<input type="file">` accepting `.csv` only
- **Submit button**

### Outputs
- **Confirmation panel** — visible on success; displays imported record count (e.g., "2 records imported")
- **Header / file error** — single error element for header mismatch, empty file, or other file-level issues
- **Row-level errors** — list of per-row errors, each naming the row number and offending field
