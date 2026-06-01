# UC4 RecommendHVACSetpointChanges — UI Design

## Part A) UI Design Summary

### Page
**`RecommendationsPage`** — `/recommendations` route. Single-page view that lets the FacilityManager pick a building, trigger a recommendation run, and view the resulting ranked recommendations.

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `recommendation-building-selector` | Populated from `GET /api/buildings` (shared with UC1/UC2/UC3) |
| "Run recommendations" button | `recommendation-run-button` | Disabled until a building is selected; disabled while a run is in flight |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Run-success panel | `recommendation-run-success` | Visible after a successful run |
| Recommendations table | `recommendation-table` | Rows ordered by rank ASC |
| Recommendation row | `recommendation-row-{rank}` | Per-row container, keyed by 1..K rank |
| Zone name cell | `recommendation-zone-name-{rank}` | |
| Setpoint delta cell | `recommendation-setpoint-delta-{rank}` | Float, 1 decimal, with leading sign |
| Projected savings cell | `recommendation-projected-savings-{rank}` | Numeric, 2 decimals (kWh) |
| Comfort impact cell | `recommendation-comfort-impact-{rank}` | One of `none`, `minor`, `moderate` |
| Run-error panel | `recommendation-run-error` | Visible only after a rejected run |
| Missing-inputs list | `recommendation-missing-inputs` | Comma-separated values from `missingInputs` array |

### Errors / Messages

- **Missing inputs:** When the API returns 400 with `missingInputs`, the page hides the success panel and shows `recommendation-run-error` with the list rendered in `recommendation-missing-inputs`. The previous successful recommendation table from earlier runs stays visible (atomicity oracle — prior data preserved).
- **Network/server error:** Generic message in `recommendation-run-error`; `recommendation-missing-inputs` is empty.
- **No building selected:** Run button stays disabled.
- **Button re-enable:** After any terminal state (success or error), `recommendation-run-button` returns to enabled (S17 oracle).

### Page lifecycle
1. On mount, fetch buildings → populate selector.
2. On building change, fetch latest recommendations for that building (`GET /api/buildings/{id}/recommendations/latest`) and render table if any rows exist.
3. On run click, `POST /api/buildings/{id}/recommendations/run`. On 200, replace table contents with response (sorted by rank ASC). On 400, show error panel; do not clear the prior table.

### Routing
Add `/recommendations` to the React Router config alongside `/register-building`, `/import-occupancy`, `/forecasts`. Update `CLAUDE.md` Per-UC browser routes block.
