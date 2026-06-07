# UC7 DetectComfortViolationRisk — UI Design

## Part A) UI Design Summary

### Page
**`ComfortRiskPage`** — `/comfort-risk` route. Single-page view that lets the FacilityManager pick a building, trigger a comfort-risk detection run, and review the decision plus per-zone alert rows (or the pass message).

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `comfort-risk-building-selector` | Populated from `GET /api/buildings` (shared with UC1–UC6). |
| "Run detection" button | `comfort-risk-run-button` | Disabled until a building is selected and no submission is in flight. |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Success banner | `comfort-risk-success-banner` | Visible after a 200 response. |
| Error banner (validation) | `comfort-risk-error-banner` | Visible on 400 / 500. |
| Missing-inputs list | `comfort-risk-missing-inputs` | Comma-separated `missingInputs`. |
| Decision pill | `comfort-risk-decision-pill` | Reads `alert` or `pass`. |
| Alerts table | `comfort-risk-alerts-table` | Visible when `decision='alert'`. |
| Alert row | `comfort-risk-alert-row-{zone_id}` | One per row in `result.alerts`. |
| Risk score cell | `comfort-risk-score-{zone_id}` | Display 3-dp `risk_score`. |
| Mitigation cell | `comfort-risk-mitigation-{zone_id}` | Verbatim mitigation string. |
| Pass message | `comfort-risk-pass-message` | Visible only when `decision='pass'`. |

### Errors / Messages

- **Validation failure (400):** Hide success banner, show `comfort-risk-error-banner` with `comfort-risk-missing-inputs` populated.
- **Server error (500):** Show `comfort-risk-error-banner` with text "Server error"; `comfort-risk-missing-inputs` empty.
- **Button re-enable:** After any terminal state (200 / 400 / 500), `comfort-risk-run-button` returns to enabled (subject to building gating).

### Page lifecycle
1. On mount → fetch buildings, populate selector, select the first by default.
2. On building change → clear any prior result/banner.
3. On submit click → `POST /api/buildings/{id}/comfort-risk/run`. On 200, render success banner, decision pill, then either the alerts table (one row per zone) or the pass message. On 400, render error banner with missing inputs. On 500, render server-error banner.

### Routing
Add `/comfort-risk` to `App.tsx` and to the `CLAUDE.md` Per-UC routes block.
