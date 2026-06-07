# UC7 DetectComfortViolationRisk — Acceptance Status

## Latest run

- **Command:** `PYTHONPATH="./backend:." behave tests/acceptance/features/UC7_DetectComfortViolationRisk.feature`
- **Date:** 2026-06-07
- **Result:** **17 / 17 scenarios passed** (302 / 302 steps, 0 skipped, 0 undefined).
- **Elapsed:** ~3.8 s.

## Full regression (UC1–UC7)

- **Command:** `PYTHONPATH="./backend:." behave tests/acceptance/features/`
- **Result:** **7 features passed**, **118 / 118 scenarios** (1611 / 1611 steps), 0 failed, 0 skipped.
- **Elapsed:** ~20.4 s.

## T4 failure-bundle cycles

**0** — single-pass T3 reached green. No failure bundle was packaged.

## Scenario index

| Scenario | Status |
|---|---|
| UC7-S01 Above-band alert for a single zone | pass |
| UC7-S02 Below-band alert for a single zone | pass |
| UC7-S03 Multi-zone mixed — one above, one below, one within | pass |
| UC7-S04 All zones within band yields a pass | pass |
| UC7-S05 Risk boundary BELOW 0.50 — no alert | pass |
| UC7-S06 Risk boundary AT 0.50 — alerted | pass |
| UC7-S07 Mitigation text shape for both directions | pass |
| UC7-S08 Unknown building rejected | pass |
| UC7-S09 No prior plan exists | pass |
| UC7-S10 Partial plan — only covered zones evaluated | pass |
| UC7-S11 Missing constraints on all zones collapses to 400 | pass |
| UC7-S12 Missing device state on one zone — skip | pass |
| UC7-S13 Cross-building isolation | pass |
| UC7-S14 Atomicity — forced DB error rolls back | pass |
| UC7-S15 Performance budget for 5-zone building | pass |
| UC7-S16 Determinism across back-to-back runs | pass |
| UC7-S17 UI flow via /comfort-risk | pass |
