# UC9 GenerateDailySavingsReport — UI Design

## Part A) UI Design Summary

### Page
**`SavingsReportPage`** — `/savings-report` route. Lets the FacilityManager pick a building, pick a `report_date`, click "Generate", and review per-zone savings, anomaly flags, and totals. Offers a client-side CSV export of the current report.

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `savings-building-selector` | Populated from `GET /api/buildings`. |
| Report date input | `savings-date-input` | `<input type="date">`; default empty so the user must pick. |
| Generate button | `savings-run-button` | Disabled until both a building and a date are selected and no submission is in flight. |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Success banner | `savings-success-banner` | Visible after a 200 response. |
| Error banner | `savings-error-banner` | Visible on 400 / 500. |
| Missing-inputs list | `savings-missing-inputs` | Comma-separated `missingInputs`. |
| Total baseline kWh | `savings-total-baseline` | Renders `response.total_baseline_kwh`. |
| Total actual kWh | `savings-total-actual` | Renders `response.total_actual_kwh`. |
| Total savings kWh | `savings-total-savings` | Renders `response.total_savings_kwh`. |
| Total savings pct | `savings-total-pct` | Renders `response.total_savings_pct` (e.g. `"20.00"`). |
| Per-zone line row | `savings-line-row-{zone_id}` | One row per line in `response.lines`. |
| Anomaly flag cell | `savings-anomaly-flag-{zone_id}` | Visible only when `line.anomaly_flag === true`. |
| Anomaly reason cell | `savings-anomaly-reason-{zone_id}` | Visible only when `line.anomaly_flag === true`. Renders `over_consumption` / `suspicious_low`. |
| Cached pill | `savings-cached-pill` | Visible only when `response.cached === true`. |
| Export CSV button | `savings-export-button` | Visible whenever a successful response is present. Triggers a client-side CSV download. |

### Errors / Messages
- **Validation failure (400):** Hide success banner; show `savings-error-banner` with `savings-missing-inputs` populated.
- **Server error (500):** Show `savings-error-banner` with text "Server error"; `savings-missing-inputs` empty.
- **Button re-enable:** After any terminal state (200 / 400 / 500), `savings-run-button` returns to enabled (subject to selector gating).

### Page lifecycle
1. On mount → fetch buildings, populate selector, select the first by default.
2. On building or date change → clear any prior result/banner.
3. On submit click → `POST /api/buildings/{building_id}/savings-reports/run` with `{report_date}`. On 200, render success banner, totals, per-zone rows, anomaly flag/reason cells where applicable, cached pill (when `cached=true`), and the export button. On 400, render error banner with missing inputs. On 500, render server-error banner.
4. On export click → build a CSV string from the response (header: `zone_id,baseline_kwh,actual_kwh,savings_kwh,savings_pct,anomaly_flag,anomaly_reason` plus a totals row) and trigger a client-side download.

### Routing
Add `/savings-report` to `App.tsx` and to the `CLAUDE.md` Per-UC routes block.
