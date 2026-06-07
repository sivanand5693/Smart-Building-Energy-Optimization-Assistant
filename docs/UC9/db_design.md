# UC9 GenerateDailySavingsReport — Database Design

## Part B) Database Design Summary

### New table: `energy_usage_records`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `building_id` | `Integer` | NOT NULL, FK → `buildings.id` ON DELETE CASCADE | |
| `zone_id` | `Integer` | NOT NULL, FK → `zones.id` ON DELETE CASCADE | |
| `usage_date` | `Date` | NOT NULL | The reporting date this row applies to. |
| `kind` | `VARCHAR(16)` | NOT NULL, CHECK `kind IN ('baseline','actual')` | |
| `kwh` | `NUMERIC(10,3)` | NOT NULL | |

**Indexes / constraints:**
- UNIQUE `(building_id, zone_id, usage_date, kind)` — one baseline + one actual per zone-day.
- `ix_energy_usage_records_building_date` on `(building_id, usage_date)` — fast lookup at run time.

### New table: `daily_savings_reports`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `building_id` | `Integer` | NOT NULL, FK → `buildings.id` ON DELETE CASCADE | |
| `report_date` | `Date` | NOT NULL | |
| `generated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Audit timestamp. |
| `total_baseline_kwh` | `NUMERIC(12,3)` | NOT NULL | |
| `total_actual_kwh` | `NUMERIC(12,3)` | NOT NULL | |
| `total_savings_kwh` | `NUMERIC(12,3)` | NOT NULL | |
| `total_savings_pct` | `NUMERIC(6,2)` | NOT NULL | Clipped to `[-100, 100]`; 0 when baseline=0. |
| `elapsed_ms` | `Integer` | NOT NULL, default `0` | Server-measured. |

**Indexes / constraints:**
- UNIQUE `(building_id, report_date)` — drives UC9 idempotency (A4).

### New table: `daily_savings_report_lines`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `report_id` | `Integer` | NOT NULL, FK → `daily_savings_reports.id` ON DELETE CASCADE | Cascade keeps header + lines consistent. |
| `zone_id` | `Integer` | NOT NULL, FK → `zones.id` ON DELETE CASCADE | |
| `baseline_kwh` | `NUMERIC(10,3)` | NOT NULL | |
| `actual_kwh` | `NUMERIC(10,3)` | NOT NULL | |
| `savings_kwh` | `NUMERIC(10,3)` | NOT NULL | |
| `savings_pct` | `NUMERIC(6,2)` | NOT NULL | |
| `anomaly_flag` | `Boolean` | NOT NULL, default `false` | A1. |
| `anomaly_reason` | `VARCHAR(32)` | NULLABLE | `over_consumption` / `suspicious_low` / NULL. |

**Indexes:** `ix_daily_savings_report_lines_report` on `(report_id)` — fast header-to-lines lookup.

### Reused tables (read-only)
- `buildings` — building existence + name (S11 oracle).
- `zones` — zone membership of the building.

### Migration
New Alembic revision chained off the UC8 head `a4c7d2e91b58`. File: `backend/alembic/versions/b6e3f8a04c19_uc9_savings_reports.py`. Creates the three new tables, the FKs, the UNIQUE constraints, the CHECK on `kind`, and the indexes. No changes to existing tables.

### Reset rules (acceptance)
Truncate list extended to **prepend** `daily_savings_report_lines`, `daily_savings_reports`, `energy_usage_records`:

```
TRUNCATE daily_savings_report_lines, daily_savings_reports,
         energy_usage_records, recommendation_explanations,
         comfort_risk_alerts, comfort_risk_runs,
         plan_adaptation_events, applied_setpoint_changes,
         setpoint_recommendations, zone_comfort_constraints,
         demand_forecasts, occupancy_records,
         operating_schedules, devices, zones, buildings
         RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- Background seeds (zones only).
- `energy_usage_records`, `daily_savings_reports`, `daily_savings_report_lines` are empty at scenario start; rows are added by the per-scenario `Given energy usage rows are ingested ...` step via `POST /api/_test/energy_usage/ingest`.

### Atomicity
The service performs the header insert + every line insert inside one SQLAlchemy session transaction. On any error the transaction rolls back; FastAPI returns 500 and zero new rows survive (S14).
