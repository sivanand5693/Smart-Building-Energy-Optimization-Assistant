# UC9 GenerateDailySavingsReport — Service / Control + Harness Design

## Part C) Service / Control Design Summary

### Application service
**`ReportingService`** — `backend/app/services/reporting_service.py`

Public method:
- `generate(building_id: int, report_date_str: str) -> DailySavingsReportResult`

Module-level constants:
- `SAVINGS_OVER_CONSUMPTION_RATIO = Decimal("1.10")`
- `SAVINGS_SUSPICIOUS_LOW_RATIO = Decimal("0.5")`

`generate` steps (single SQLAlchemy session, single commit at the end):
1. Parse `report_date_str` (`YYYY-MM-DD`). Failure → raise `SavingsInputsMissing(["report_date"])`.
2. Load the `BuildingModel` row + its zones. Missing building → `SavingsInputsMissing(["building"])`.
3. Cache check: `SavingsReportRepository.get_for_building_date(building_id, report_date)`. If present → return a cached `DailySavingsReportResult(cached=True, elapsed_ms=<lookup-time>)`; no further work.
4. Probe per-zone baseline + actual rows via `EnergyUsageRepository.for_building_date(building_id, report_date)`. Accumulate `baseline` and/or `actual` into `missing` for any zone that lacks one. If non-empty → `SavingsInputsMissing(sorted(set(missing)))`.
5. Compute per-zone lines (A5) and anomaly flags (A1). Accumulate totals.
6. If `_force_db_error_flag` is set, raise `SavingsForcedDbError` (S14).
7. Persist via `SavingsReportRepository.save_no_commit(header, lines)`, then `db.commit()`.
8. Return `DailySavingsReportResult` carrying header fields + lines + `cached=False`, `elapsed_ms` (server-measured), `generated_at`.

Atomicity: any exception → `db.rollback()` + re-raise.

### Domain types — `backend/app/domain/savings_report.py`
- `DailySavingsReportLine` (dataclass): `zone_id: int`, `baseline_kwh: Decimal`, `actual_kwh: Decimal`, `savings_kwh: Decimal`, `savings_pct: Decimal`, `anomaly_flag: bool`, `anomaly_reason: str | None`.
- `DailySavingsReportResult` (dataclass): `report_id: int | None`, `building_id: int`, `report_date: date`, `total_baseline_kwh: Decimal`, `total_actual_kwh: Decimal`, `total_savings_kwh: Decimal`, `total_savings_pct: Decimal`, `lines: list[DailySavingsReportLine]`, `cached: bool`, `elapsed_ms: float`, `generated_at: datetime | None`.
- `SavingsInputsMissing(Exception)` with `missing_inputs: list[str]`.
- `SavingsForcedDbError(Exception)` — test lever.

### Repositories
**`EnergyUsageRepository`** — `backend/app/infrastructure/repositories/energy_usage_repository.py`
- `ingest(rows: list[EnergyUsageRecordModel]) -> None` — upsert-style insert; on conflict update kwh.
- `for_building_date(building_id: int, usage_date: date) -> list[EnergyUsageRecordModel]`.

**`SavingsReportRepository`** — `backend/app/infrastructure/repositories/savings_report_repository.py`
- `save_no_commit(header: DailySavingsReportModel, lines: list[DailySavingsReportLineModel]) -> None` — add + flush, caller commits.
- `get_for_building_date(building_id: int, report_date: date) -> DailySavingsReportModel | None`.
- `lines_for_report(report_id: int) -> list[DailySavingsReportLineModel]`.
- `count_reports_for(building_id: int, report_date: date) -> int`.
- `count_lines_for(building_id: int, report_date: date) -> int`.

### Models — `backend/app/infrastructure/models/energy_usage_models.py`
Three SQLAlchemy models:
- `EnergyUsageRecordModel` — table `energy_usage_records`.
- `DailySavingsReportModel` — table `daily_savings_reports`.
- `DailySavingsReportLineModel` — table `daily_savings_report_lines`.

Re-exported from `app.infrastructure.models.__init__`.

### API routes — `backend/app/api/routes/reporting.py` (new; register in `main.py`)
- `POST /api/buildings/{building_id}/savings-reports/run` body `{"report_date": "YYYY-MM-DD"}` → 200 `DailySavingsReportResponse`, 400 `{detail:{missingInputs:[...]}}`, 500.
- `GET /api/buildings/{building_id}/savings-reports?date=YYYY-MM-DD` → 200 cached `DailySavingsReportResponse` | 404.

`DailySavingsReportResponse` Pydantic model fields: `report_id`, `building_id`, `report_date`, `total_baseline_kwh`, `total_actual_kwh`, `total_savings_kwh`, `total_savings_pct`, `lines` (list of `DailySavingsReportLineResponse`), `cached` (bool), `elapsed_ms` (float), `generated_at` (datetime, nullable).

### Test-support endpoints (added to `app/api/routes/test_support.py`)
- `POST /api/_test/energy_usage/ingest` — body: list of `{building_id, zone_id, usage_date, kind, kwh}`. Inserts (or upserts on the UNIQUE) rows; used by every UC9 scenario that establishes baseline+actual.
- `POST /api/_test/savings/force_db_error` — toggles the service flag so the next `generate()` raises `SavingsForcedDbError` mid-write.

---

## Part D) Acceptance Harness Design

### Environment hooks (`tests/acceptance/environment.py`)
No change beyond extending the DB truncate (covered in `database_reset.py`).

### Test doubles
None new. UC9 has no external adapter — its only inputs are DB rows that the test-support endpoint seeds directly.

### Step definitions (`tests/acceptance/steps/UC9_steps.py`)
Reuses background steps from UC1/UC3:
- `Given the system is initialized for acceptance testing`
- `Given a building "<name>" exists with zones:` (table)

New UC9 steps:

| Step | Action |
|---|---|
| `Given energy usage rows are ingested for "<bldg>" on "<date>":` (table) | For each row, POST to `/api/_test/energy_usage/ingest`. Empty `baseline_kwh` / `actual_kwh` cells are skipped (so the missing-input scenarios work). |
| `Given the ReportingService is configured to force a DB error on the next request` | POST `/api/_test/savings/force_db_error`. |
| `When the FacilityManager generates a savings report for "<bldg>" on "<date>"` | POST `/api/buildings/{bid}/savings-reports/run` `{report_date}`. Stash response. |
| `When the FacilityManager generates a savings report for unknown building id <id> on "<date>"` | POST with the literal id. |
| `When the FacilityManager generates a savings report for "<bldg>" with report_date "<date>"` | POST with the literal `report_date` string (used by S12 invalid-date). |
| `Then the savings report response status is <code>` | assert status. |
| `Then the savings report has total_savings_kwh "<v>"` / `total_savings_pct` / `total_baseline_kwh` / `total_actual_kwh` | exact string equality on the formatted numeric field. |
| `Then the savings report total_savings_kwh equals the sum of per-line savings_kwh` | sum lines, assert equal (Decimal). |
| `Then the savings report line for zone "<z>" of "<b>" has savings_kwh "<v>" and savings_pct "<p>"` | lookup line, exact equality. |
| `Then the savings report line for zone "<z>" of "<b>" has anomaly_flag "<bool>"` | `bool(line.anomaly_flag) == expected`. |
| `Then the savings report line for zone "<z>" of "<b>" has anomaly_reason "<r>"` | `line.anomaly_reason == expected`. |
| `Then the savings report response missingInputs equals <list>` | `body.detail.missingInputs == json.loads(list)`. |
| `Then the savings report response has cached "<bool>"` | `bool(body.cached) == expected`. |
| `Then the savings report response elapsed_ms is under <ms>` | `body.elapsed_ms < ms`. |
| `Then the database contains <n> daily_savings_reports row(s) for "<bldg>" on "<date>"` | SQL count via test engine. |
| `Then the database contains <n> daily_savings_report_lines rows for "<bldg>" on "<date>"` | SQL count via test engine joined on header. |
| `When the user generates a savings report for "<b>" on "<date>" via the SavingsReportPage` / `again` | Playwright drive `/savings-report`. |
| `Then the SavingsReportPage shows the success banner` / `totals` / `line row` / `anomaly flag` / `cached pill` / `export button` | Playwright selector waits. |

---

## Part E) Traceability Table

| Scenario | UI elements | DB elements | Service / Adapter |
|---|---|---|---|
| UC9-S01 Happy single-zone | n/a | 1 header + 1 line | per-line math + no anomaly |
| UC9-S02 Multi-zone totals | n/a | 1 header + 3 lines | totals == Σ lines |
| UC9-S03 Over-consumption anomaly | n/a | 1 header + 1 line | anomaly_flag=true, reason=over_consumption |
| UC9-S04 Suspicious-low anomaly | n/a | 1 header + 1 line | anomaly_flag=true, reason=suspicious_low |
| UC9-S05 Anomaly boundaries | n/a | 1 header + 4 lines | exact ratios → no anomaly; +0.001 → anomaly |
| UC9-S06 Zero baseline | n/a | 1 header + 1 line | pct=0, no anomaly |
| UC9-S07 Negative savings within thresholds | n/a | 1 header + 1 line | savings_kwh<0, no anomaly |
| UC9-S08 Missing baseline | n/a | 0 rows | missingInputs=["baseline"] |
| UC9-S09 Missing actual | n/a | 0 rows | missingInputs=["actual"] |
| UC9-S10 Both missing — sorted | n/a | 0 rows | missingInputs=["actual","baseline"] |
| UC9-S11 Unknown building | n/a | 0 rows | missingInputs=["building"] |
| UC9-S12 Invalid date | n/a | 0 rows | missingInputs=["report_date"] |
| UC9-S13 Idempotency | n/a | 1 header + 1 line across 2 POSTs | cached=true on 2nd |
| UC9-S14 Atomicity | n/a | 0 rows after 500 | force_db_error → rollback |
| UC9-S15 Performance | n/a | 1 header + 5 lines | elapsed_ms < 5000 |
| UC9-S16 Cross-building | n/a | 1 header for A, 0 for B | scoping by building_id |
| UC9-S17 UI flow | banner, totals, line row, anomaly flag, cached pill, export button | 1 header + 1 line | `/savings-report` page |
