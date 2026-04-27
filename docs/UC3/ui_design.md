# UC3 ForecastZoneDemand — UI Design

## Part A) UI Design Summary

### Page
**`ForecastsPage`** — `/forecasts` route. Single-page view that lets the user pick a building, manually trigger a forecast run (the test surface for the Scheduler — see A4 in `structured_requirement.md`), and view the resulting per-zone forecasts.

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `forecast-building-selector` | Populated from `GET /api/buildings`; same client used by UC2 |
| "Run forecast" button | `run-forecast-button` | Disabled until a building is selected; disabled while a run is in flight |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Run-success panel | `forecast-run-success` | Visible after a successful run; shows building name + run timestamp |
| Forecast table | `forecast-table` | One row per zone for the latest run |
| Forecast row | `forecast-row-{zone_id}` | Per-row container |
| Zone name cell | `forecast-zone-name-{zone_id}` | |
| Predicted kWh cell | `forecast-predicted-kwh-{zone_id}` | Numeric, 2 decimals |
| Timestamp cell | `forecast-timestamp-{zone_id}` | ISO-8601 string |
| Run-error panel | `forecast-run-error` | Visible only after a rejected run |
| Missing-inputs list | `forecast-missing-inputs` | Comma-separated values from `missingInputs` array (e.g. `occupancy, weather`) |

### Errors / Messages

- **Missing inputs:** When the API returns 400 with `missingInputs`, the page hides the success panel and shows `forecast-run-error` with the list rendered in `forecast-missing-inputs`. Any previous successful forecast table from earlier runs stays visible (atomicity oracle — prior data is preserved).
- **Network/server error:** Generic message in `forecast-run-error`; `forecast-missing-inputs` is empty.
- **No building selected:** Run button stays disabled — no error needed.

### Page lifecycle
1. On mount, fetch buildings list → populate selector.
2. On building change, fetch latest forecasts for that building (`GET /api/buildings/{id}/forecasts/latest`) and render table if any rows exist. Empty result hides the table — no error.
3. On run click, `POST /api/buildings/{id}/forecasts/run`. On 200, replace table contents with response. On 400, show error panel; do not clear the prior table.

### Routing
Add `/forecasts` to the React Router config alongside `/buildings` (UC1) and `/occupancy` (UC2). Add a top-nav link "Forecasts".
