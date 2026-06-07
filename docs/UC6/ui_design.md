# UC6 AdaptPlanToOccupancyChange — UI Design

## Part A) UI Design Summary

### Page
**`AdaptPlanPage`** — `/adapt-plan` route. Single-page view that lets the FacilityManager pick a building, type a new occupancy count per zone, submit the adapt request, and view the decision, reason, changed zones, and the resulting revised-recs table.

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `adapt-building-selector` | Populated from `GET /api/buildings` (shared with UC1–UC5) |
| Per-zone row | `adapt-zone-row-{zone_id}` | One per zone of the selected building |
| Per-zone occupancy input | `adapt-occupancy-input-{zone_id}` | Number input, blank means "skip this zone in the payload" |
| "Submit adapt" button | `adapt-run-button` | Disabled until a building is selected, at least one input has a numeric value, and no submission is in flight |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Success banner | `adapt-success-banner` | Visible after a 200 response |
| Error banner (validation) | `adapt-error-banner` | Visible on 400 |
| Missing-inputs list | `adapt-missing-inputs` | Comma-separated `missingInputs` |
| Decision pill | `adapt-decision-pill` | Reads `replanned` or `no_replan` |
| Reason text | `adapt-reason-text` | Verbatim service `reason` |
| Changed-zone chip | `adapt-changed-zone-{zone_id}` | One per zone in `changed_zone_ids` |
| Revised-recs table | `adapt-revised-recs-table` | Visible whenever the latest run has rows |
| Revised-recs row | `adapt-revised-rec-row-{rank}` | One per row in `GET /recommendations/latest` after the adapt |

### Errors / Messages

- **Validation failure (400):** Hide `adapt-success-banner`, show `adapt-error-banner` with `adapt-missing-inputs` populated.
- **Server error (500):** Show `adapt-error-banner` with text "Server error"; `adapt-missing-inputs` empty.
- **Button re-enable:** After any terminal state (200 / 400 / 500), `adapt-run-button` returns to enabled (subject to building+input gating).

### Page lifecycle
1. On mount → fetch buildings, populate selector.
2. On building change → fetch zones (via the selected building summary) and render one row per zone with a blank occupancy input.
3. On submit click → `POST /api/buildings/{id}/plan/adapt` with `{occupancy_changes: [...]}`. Blanks are filtered out client-side. On 200, render success banner, decision pill, reason, changed-zone chips, then refetch `GET /recommendations/latest` and render the revised-recs table. On 400, render error banner with missing inputs. On 500, render server-error banner.

### Routing
Add `/adapt-plan` to `App.tsx` and to the `CLAUDE.md` Per-UC routes block.
