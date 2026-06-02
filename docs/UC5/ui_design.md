# UC5 ApplyApprovedEnergyPlan — UI Design

## Part A) UI Design Summary

### Page
**`ApplyPlanPage`** — `/apply-plan` route. Single-page view that lets the FacilityManager pick a building, see the latest UC4 recommendation run, approve a subset (or all), trigger an apply, and view per-line execution outcomes.

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `apply-building-selector` | Populated from `GET /api/buildings` (shared with UC1–UC4) |
| Per-row approval checkbox | `apply-approve-{rank}` | One per latest-run recommendation; default checked when the run loads |
| "Apply selected" button | `apply-run-button` | Disabled until a building is selected, at least one row is checked, and no apply is in flight |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Latest-run table | `latest-run-table` | Rows from `GET /api/buildings/{id}/recommendations/latest` ordered by rank ASC |
| Latest-run row | `latest-run-row-{rank}` | Per-row container for the approval checkboxes |
| Apply result table | `apply-result-table` | Visible after a 200 apply response |
| Apply result row | `apply-result-row-{index}` | One per result, ordered as returned by the API (rank ASC) |
| Apply status pill | `apply-status-{index}` | Reads `dispatched` or `failed` |
| Apply error label | `apply-error-{index}` | Visible only when status is `failed`; carries `error_code` |
| Success banner | `apply-success-banner` | Visible when at least one result row is `dispatched` |
| Error banner (validation) | `apply-error-banner` | Visible on 400 |
| Missing-inputs list | `apply-missing-inputs` | Comma-separated `missingInputs` |

### Errors / Messages

- **Validation failure (400):** Hide `apply-result-table`, hide `apply-success-banner`, show `apply-error-banner` with `apply-missing-inputs` populated. The latest-run table stays visible.
- **Server error (500):** Show `apply-error-banner` with text "Server error"; `apply-missing-inputs` empty. The latest-run table stays visible.
- **Button re-enable:** After any terminal state (200 / 400 / 500), `apply-run-button` returns to enabled (subject to building+selection gating).

### Page lifecycle
1. On mount → fetch buildings, populate selector.
2. On building change → fetch latest recommendations and render `latest-run-table` with approval checkboxes (all checked by default).
3. On apply click → `POST /api/buildings/{id}/plans/apply` with `{recommendation_ids: [...]}`. On 200, render `apply-result-table` (preserve latest-run table). On 400, render error banner. On 500, render server-error banner.

### Routing
Add `/apply-plan` to `App.tsx` and to the `CLAUDE.md` Per-UC routes block.
