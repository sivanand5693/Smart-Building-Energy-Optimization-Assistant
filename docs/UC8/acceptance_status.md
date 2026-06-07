# UC8 ExplainRecommendation — Acceptance Status

| Metric | Value |
|---|---|
| Feature file | `tests/acceptance/features/UC8_ExplainRecommendation.feature` |
| Total scenarios | 17 |
| Passing | 17 |
| Failing | 0 |
| T4 cycles required | 0 |
| Last run | 2026-06-07 |
| Full-suite regression | 135 / 135 scenarios passing across UC1–UC8 |

## Run command

```
PYTHONPATH="./backend:." behave tests/acceptance/features/UC8_ExplainRecommendation.feature
```

## Scenario roll-up

| Scenario | Status |
|---|---|
| UC8-S01 Happy path — text references all three factors and the numeric savings | PASS |
| UC8-S02 Factors JSON shape — keys energy, comfort, occupancy each non-empty | PASS |
| UC8-S03 Idempotency — second call is cached and the adapter is not re-invoked | PASS |
| UC8-S04 Determinism — identical inputs across two recommendations produce identical text | PASS |
| UC8-S05 Unknown recommendation_id is rejected with no row written | PASS |
| UC8-S06 Missing comfort constraints for the zone yields a 400 | PASS |
| UC8-S07 Missing occupancy records for the zone yields a 400 | PASS |
| UC8-S08 Missing forecast row for the zone yields a 400 | PASS |
| UC8-S09 Multiple missing inputs accumulate and are returned sorted alphabetically | PASS |
| UC8-S10 Cross-building isolation — explain on A doesn't touch B | PASS |
| UC8-S11 Quality Q1 — text contains comfort_impact word and occupancy count value | PASS |
| UC8-S12 Quality Q2 — first-generation elapsed_ms is under 4000 | PASS |
| UC8-S13 Cached response elapsed_ms is under 500 | PASS |
| UC8-S14 Atomicity — forced DB error rolls back, zero rows survive | PASS |
| UC8-S15 Model version persisted and surfaced | PASS |
| UC8-S16 GET endpoint returns the cached row when present, 404 otherwise | PASS |
| UC8-S17 UI flow via /explain | PASS |

T4 was not needed — the implementation passed the suite on the first run.
