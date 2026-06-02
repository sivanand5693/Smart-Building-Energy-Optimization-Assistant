# UC5 ApplyApprovedEnergyPlan — Acceptance Status

- **Date:** 2026-06-01
- **Result:** 17 / 17 scenarios pass
- **T4 cycles:** 0
- **Failure bundles:** none
- **Regression:** 84 / 84 across UC1+UC2+UC3+UC4+UC5

## Scenarios

| ID | Title | Status |
|---|---|---|
| UC5-S01 | Happy single-rec apply | pass |
| UC5-S02 | Happy multi-rec apply across zones in rank order | pass |
| UC5-S03 | Approve all recommendations of the latest run | pass |
| UC5-S04 | Single-zone boundary apply-all | pass |
| UC5-S05 | Multi-zone boundary apply-all | pass |
| UC5-S06 | Result row field structure | pass |
| UC5-S07 | Unknown building id | pass |
| UC5-S08 | Unknown recommendation id | pass |
| UC5-S09 | Cross-building recommendation id | pass |
| UC5-S10 | Idempotency on re-apply (adapter NOT re-invoked) | pass |
| UC5-S11 | Stale-run rejection | pass |
| UC5-S12 | Missing HVAC device for one zone (siblings still dispatched) | pass |
| UC5-S13 | Adapter failure for one line (siblings still dispatched) | pass |
| UC5-S14 | Cross-building isolation | pass |
| UC5-S15 | DB-error atomicity → 500, zero new rows | pass |
| UC5-S16 | Performance budget for 10-rec batch | pass |
| UC5-S17 | UI execution summary | pass |

## Evidence
- `PYTHONPATH="./backend:." behave tests/acceptance/features/UC5_ApplyApprovedEnergyPlan.feature` → 17 / 17 pass, 291 steps, 3.24s.
- Regression UC1–UC5 → 84 / 84 pass, 1019 steps, 14.28s.
- Migration head: `c7d2a1f9e5b0` (chained off UC4 head `a91c2f3d7e84`).
