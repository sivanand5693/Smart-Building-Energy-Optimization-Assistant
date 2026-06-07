# UC9 GenerateDailySavingsReport — Structured Requirement

## A) Structured Requirement

**Use case name:** GenerateDailySavingsReport

**Participating actors:**
- FacilityManager (primary; activates "Generate Daily Savings Report" for a building + report_date).
- ReportingService (control).
- EnergyUsageRecordStore (DB-backed; **new** `energy_usage_records` table — baseline + actual per `(building_id, zone_id, usage_date, kind)`, UNIQUE).
- DailySavingsReportStore (DB-backed; **new** `daily_savings_reports` table — header row UNIQUE per `(building_id, report_date)`).
- DailySavingsReportLineStore (DB-backed; **new** `daily_savings_report_lines` table — per-zone breakdown rows, FK to header with `ON DELETE CASCADE`).

**Goal:** When the FacilityManager activates "Generate Daily Savings Report" for a building and `report_date`, the system loads baseline and actual energy usage rows for every zone of the building on that date, computes per-zone savings + anomaly flags (A1) plus building-wide totals, atomically writes one `daily_savings_reports` row plus one `daily_savings_report_lines` row per zone, and returns a `DailySavingsReportResult`. Re-running for the same `(building_id, report_date)` returns the cached header + lines with `cached=true`; no recomputation, no new rows.

**Preconditions:**
- The target building has at least one zone.
- For the requested `report_date`, every zone has both a `baseline` and an `actual` row in `energy_usage_records`.
- Baseline and actual rows are ingested via the test-support endpoint `POST /api/_test/energy_usage/ingest` (A2; real-meter ingestion deferred).

**Trigger boundary:** `POST /api/buildings/{building_id}/savings-reports/run` body `{"report_date": "YYYY-MM-DD"}`.

**Main success flow:**
1. The FacilityManager (or any caller) POSTs the run endpoint with the target `building_id` and `report_date`.
2. The system validates the building exists (else 400 `missingInputs=["building"]`) and the date parses (else 400 `missingInputs=["report_date"]`).
3. The system loads every zone of the building and, for `report_date`, probes baseline + actual rows per zone. Any zones with no baseline contribute `baseline` to `missingInputs`; any zones with no actual contribute `actual`. The labels are deduplicated and sorted alphabetically. If non-empty → 400, zero rows written.
4. The system checks `daily_savings_reports` for an existing `(building_id, report_date)` row. If present → return the cached header + lines with `cached=true`, `elapsed_ms=<lookup time>` (near zero); no recomputation, no new rows (A4).
5. Otherwise the system computes per-zone savings (A5) and anomaly flags (A1), totals over zones, and persists the header row plus one line per zone in a single SQLAlchemy transaction (A6). Commit.
6. Return `DailySavingsReportResult` carrying the report id, building_id, report_date, totals, lines, `cached=false`, `elapsed_ms` (server-measured), `generated_at`.
7. FacilityManager reviews on `/savings-report`; optional CSV export is performed client-side (A9).

**Success postconditions:**
- Exactly one `daily_savings_reports` row exists for `(building_id, report_date)`.
- The number of `daily_savings_report_lines` rows for that header equals the number of zones in the building.
- Repeat POSTs return `cached=true` with the same totals and the table counts unchanged.

**Failure postconditions:**
- On any `missingInputs` 400: zero new rows in any of the three new tables.
- On a forced mid-write DB error (test lever): the transaction rolls back; header + line counts unchanged; 500 response.

**Quality requirements:**
- Q1: Savings are reported as numeric fields (`total_savings_kwh`, `total_savings_pct`, per-line `savings_kwh`, `savings_pct`).
- Q2: Server-measured `elapsed_ms < 5000` (A7).
- Q3: Atomicity — header + lines persist together or not at all (A6, S14).

### Numbered Assumptions

- **A1** Anomaly rule: a per-zone row is an anomaly when `actual_kwh > baseline_kwh * 1.10` (`anomaly_reason='over_consumption'`) OR `actual_kwh < baseline_kwh * 0.5` (`anomaly_reason='suspicious_low'`). Constants `SAVINGS_OVER_CONSUMPTION_RATIO = 1.10` and `SAVINGS_SUSPICIOUS_LOW_RATIO = 0.5` live in `app.services.reporting_service`. When `baseline_kwh == 0` the ratio rule does not apply and the row is **not** flagged.
- **A2** Both baseline and actual energy usage rows are ingested via the test-support endpoint `POST /api/_test/energy_usage/ingest` (body: list of `{building_id, zone_id, usage_date, kind, kwh}`). Real-meter / smart-grid ingestion is **deferred**.
- **A3** "Reporting day" = the `report_date` from the request. Every zone of the building must have BOTH a baseline AND an actual row for that date — otherwise the API returns 400 `missingInputs=[...]` listing every gap (`baseline` and/or `actual`), sorted alphabetically and deduplicated; zero rows are written.
- **A4** Idempotency: `(building_id, report_date)` is UNIQUE on `daily_savings_reports`. A repeat POST returns the cached header + lines with `cached=true`, `elapsed_ms` near zero; no recomputation; row count is unchanged.
- **A5** Savings formula: `savings_kwh = baseline_kwh - actual_kwh`; `savings_pct = (baseline_kwh - actual_kwh) / baseline_kwh * 100`, clipped to `[-100.00, 100.00]`. If `baseline_kwh == 0` then `savings_pct = 0` (avoid divide-by-zero). Totals are computed by summing per-zone numeric fields and then computing `total_savings_pct` from `total_baseline_kwh` / `total_actual_kwh` with the same clipping + zero-baseline rule.
- **A6** Atomicity: the header row + all per-zone line rows commit together in a single SQLAlchemy transaction. On any DB error the transaction rolls back; zero new rows survive (S14).
- **A7** Quality Q2 = `elapsed_ms < 5000` for both fresh-generation and cached responses.
- **A8** Exit path "usage data is incomplete and no report is generated" maps to the 400 `missingInputs` branch (A3). There is no partial-report path.
- **A9** Export: CSV is generated client-side from the API response. There is no server-side export endpoint.
- **A10** Performance scenario (S15) uses a 5-zone building so the `elapsed_ms < 5000` budget is exercised with non-trivial line counts.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| Happy single-zone savings math | 200 + line.savings_kwh=20, savings_pct=20.00, anomaly_flag=false | S01 |
| Happy multi-zone totals match line sum | 200 + totals = Σ lines | S02 |
| Over-consumption anomaly (actual > baseline*1.10) | line.anomaly_flag=true, anomaly_reason='over_consumption' | S03 |
| Suspicious-low anomaly (actual < baseline*0.5) | line.anomaly_flag=true, anomaly_reason='suspicious_low' | S04 |
| Anomaly boundary conditions (= 1.10 and = 0.5 ratios) | exact ratios → no anomaly; +0.001 over → anomaly | S05 |
| Zero baseline edge | savings=-actual, pct=0, anomaly_flag=false | S06 |
| Negative savings (actual > baseline but within thresholds) | line.savings_kwh negative, anomaly_flag=false | S07 |
| Missing baseline for a zone | 400 missingInputs=["baseline"], zero rows written | S08 |
| Missing actual for a zone | 400 missingInputs=["actual"], zero rows written | S09 |
| Both missing — sorted, deduplicated | 400 missingInputs=["actual","baseline"], zero rows written | S10 |
| Unknown building | 400 missingInputs=["building"] | S11 |
| Invalid date format | 400 missingInputs=["report_date"] | S12 |
| Idempotency — cached re-run | 200 + cached=true, header + line counts unchanged | S13 |
| Atomicity — forced DB error mid-write | 500 + zero new rows | S14 |
| Performance — 5-zone elapsed_ms < 5000 | 200 + body.elapsed_ms < 5000 | S15 |
| Cross-building isolation | run for A doesn't write rows for B | S16 |
| UI flow via /savings-report | totals + per-zone rows + anomaly flag/reason + cached pill + export button | S17 |

## C) Acceptance Oracles

- **Persistence oracle:** After a successful run, exactly one `daily_savings_reports` row exists for `(building_id, report_date)` and exactly `len(zones)` `daily_savings_report_lines` rows exist for that header.
- **Idempotency oracle:** On the second POST for the same `(building_id, report_date)`, the response carries `cached=true`, no new rows are written, and the totals are unchanged (S13).
- **Anomaly oracle:** For a line, `anomaly_flag` is true iff `actual_kwh > baseline_kwh * 1.10` OR `actual_kwh < baseline_kwh * 0.5`, AND `baseline_kwh > 0`; the matching `anomaly_reason` is `'over_consumption'` or `'suspicious_low'` (S03, S04, S05).
- **Missing-inputs oracle:** The 400 response carries `detail.missingInputs` whose entries are drawn from the closed set `{building, report_date, baseline, actual}`, sorted alphabetically and deduplicated (S08–S12).
- **Atomicity oracle:** On a forced 500 mid-write, header + line row counts for the target `(building_id, report_date)` remain zero (S14).
- **Cross-building oracle:** A run for building A does not write any header or line rows tied to building B (S16).
- **Quality oracle Q2:** `body.elapsed_ms < 5000` (S15).
- **Math oracles:**
  - Per-line: `savings_kwh == baseline_kwh - actual_kwh`; `savings_pct == ((baseline - actual) / baseline * 100)` clipped to `[-100, 100]`, or 0 when `baseline == 0` (S01, S06, S07).
  - Totals: `total_baseline_kwh = Σ baseline`, `total_actual_kwh = Σ actual`, `total_savings_kwh = total_baseline - total_actual`, `total_savings_pct` from those totals via the same formula (S02).
- **UI oracle:** `/savings-report` renders `savings-success-banner`, `savings-total-baseline`, `savings-total-actual`, `savings-total-savings`, `savings-total-pct`, one `savings-line-row-{zone_id}` per zone, an `savings-anomaly-flag-{zone_id}` cell on anomaly lines, and an `savings-export-button`. On the second submit, `savings-cached-pill` is visible (S17).

## D) Deferred Scope (Recap)

- Real-meter / smart-grid ingestion for `energy_usage_records` — only the test-support endpoint exists (A2).
- Server-side CSV export — export is performed client-side from the API body (A9).
- Multi-day rollup reports or trend analytics — UC9 produces one report per `(building_id, report_date)`.
- Per-user authentication / authorization — the run endpoint is invocable by any caller in the test harness.
- Automatic scheduled generation — UC9 runs only on the POST trigger.
