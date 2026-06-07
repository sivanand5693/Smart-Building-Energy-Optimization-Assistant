# UC8 ExplainRecommendation — UI Design

## Part A) UI Design Summary

### Page
**`ExplainPage`** — `/explain` route. Optionally driven by `?recommendation_id=X` query parameter. Lets the FacilityManager pick a building, pick a recommendation from the latest run, click "Explain Recommendation", and read the explanation card.

### Inputs

| Element | `data-testid` | Notes |
|---|---|---|
| Building selector dropdown | `explain-building-selector` | Populated from `GET /api/buildings`. |
| Recommendation selector dropdown | `explain-recommendation-selector` | Populated from `GET /api/buildings/{id}/recommendations/latest`. Pre-selects the value from the `?recommendation_id=` query param when present. |
| "Explain" button | `explain-run-button` | Disabled until a recommendation is selected and no submission is in flight. |

### Outputs

| Element | `data-testid` | Notes |
|---|---|---|
| Success banner | `explain-success-banner` | Visible after a 200 response. |
| Error banner | `explain-error-banner` | Visible on 400 / 500. |
| Missing-inputs list | `explain-missing-inputs` | Comma-separated `missingInputs`. |
| Explanation text | `explain-text` | Renders `response.text` verbatim inside a styled card. |
| Energy factor cell | `explain-factor-energy` | Renders `response.factors.energy`. |
| Comfort factor cell | `explain-factor-comfort` | Renders `response.factors.comfort`. |
| Occupancy factor cell | `explain-factor-occupancy` | Renders `response.factors.occupancy`. |
| Cached pill | `explain-cached-pill` | Visible only when `response.cached === true`. |
| Model-version pill | `explain-model-version` | Renders `response.model_version` verbatim. |

### Errors / Messages
- **Validation failure (400):** Hide success banner, show `explain-error-banner` with `explain-missing-inputs` populated.
- **Server error (500):** Show `explain-error-banner` with text "Server error"; `explain-missing-inputs` empty.
- **Button re-enable:** After any terminal state (200 / 400 / 500), `explain-run-button` returns to enabled (subject to recommendation gating).

### Page lifecycle
1. On mount → fetch buildings, populate selector, select the first by default. Read `?recommendation_id=` query param.
2. On building change → clear any prior result/banner; fetch the latest recommendations for the building; populate the recommendation selector; pre-select either the queried id or the first row.
3. On recommendation change → clear any prior result/banner.
4. On submit click → `POST /api/recommendations/{recommendation_id}/explain`. On 200, render success banner, explanation text card, three factor cells, model-version pill, and the cached pill when `cached=true`. On 400, render error banner with missing inputs. On 500, render server-error banner.

### Routing
Add `/explain` to `App.tsx` and to the `CLAUDE.md` Per-UC routes block. The existing `ExplanationPage` directory remains empty/unused; the locked plan uses a new `ExplainPage` directory.
