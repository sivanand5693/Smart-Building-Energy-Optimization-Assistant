# UC7 DetectComfortViolationRisk — Database Design

## Part B) Database Design Summary

### New table: `comfort_risk_runs`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `building_id` | `Integer` | NOT NULL, FK → `buildings.id` ON DELETE CASCADE | |
| `run_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Audit / ordering. |
| `decision` | `String(8)` | NOT NULL, CHECK in (`alert`,`pass`) | Outcome of the materiality test. |
| `alerts_count` | `Integer` | NOT NULL, default `0` | Count of `comfort_risk_alerts` rows for the run. |
| `elapsed_ms` | `Integer` | NOT NULL, default `0` | Server-reported elapsed time. |
| `source_run_timestamp` | `TIMESTAMPTZ` | NOT NULL | The `run_timestamp` of the `setpoint_recommendations` snapshot the projection came from (A3). |

**Indexes:**
- `(building_id, run_at DESC)` — fast "latest run for building" lookups.

### New table: `comfort_risk_alerts`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `run_id` | `Integer` | NOT NULL, FK → `comfort_risk_runs.id` ON DELETE CASCADE | |
| `zone_id` | `Integer` | NOT NULL, FK → `zones.id` ON DELETE CASCADE | |
| `projected_temp_f` | `Numeric(5,2)` | NOT NULL | `current_setpoint_f + setpoint_delta_f`. |
| `occupied_min_f` | `Numeric(5,2)` | NOT NULL | Snapshot of `zone_comfort_constraints.occupied_min_f`. |
| `occupied_max_f` | `Numeric(5,2)` | NOT NULL | Snapshot of `zone_comfort_constraints.occupied_max_f`. |
| `risk_score` | `Numeric(4,3)` | NOT NULL | Clipped to `[0.000, 1.000]`. |
| `direction` | `String(8)` | NOT NULL, CHECK in (`above`,`below`) | Which side of the band was exceeded. |
| `mitigation` | `Text` | NOT NULL | Templated NL string per A4. |

**Indexes:**
- `(run_id)` — fast "alerts for run" lookups.

### Reused tables
- `buildings`, `zones` — read-only context.
- `setpoint_recommendations` — read-only; latest run per building resolves the projected delta per zone.
- `zone_comfort_constraints` — read-only; defines the occupied band per zone.

### Migration
New Alembic revision chained off the UC6 head `e8a5c4d62a7f`. File: `backend/alembic/versions/f9b3e7a82c41_uc7_comfort_risk.py`. Creates both tables, the CHECK constraints, the FKs, and the two indexes. No changes to existing tables.

### Reset rules (acceptance)
Truncate list extended to **prepend** `comfort_risk_alerts` and `comfort_risk_runs` so CASCADE order is safe:

```
TRUNCATE comfort_risk_alerts, comfort_risk_runs, plan_adaptation_events,
         applied_setpoint_changes, setpoint_recommendations,
         zone_comfort_constraints, demand_forecasts, occupancy_records,
         operating_schedules, devices, zones, buildings RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- Background seeds: building tree, occupancy snapshots, weather + device-state doubles (now including `setpoint_f`), demand forecasts, comfort constraints, and a prior UC4 recommendation run.
- `comfort_risk_runs` and `comfort_risk_alerts` are empty at scenario start.

### Atomicity
The service performs all writes — the `comfort_risk_runs` row plus the N `comfort_risk_alerts` rows — inside a **single SQLAlchemy session transaction**. On any error the transaction is rolled back; FastAPI returns 500 and zero new rows survive (S14).
