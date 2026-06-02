# UC5 ApplyApprovedEnergyPlan — Database Design

## Part B) Database Design Summary

### New table: `applied_setpoint_changes`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `recommendation_id` | `Integer` | NOT NULL, UNIQUE, FK -> `setpoint_recommendations.id` ON DELETE CASCADE | Idempotency key (A3) |
| `building_id` | `Integer` | NOT NULL, FK -> `buildings.id` ON DELETE CASCADE | Cached for cross-building isolation queries |
| `zone_id` | `Integer` | NOT NULL, FK -> `zones.id` ON DELETE CASCADE | Cached for per-zone result assertions |
| `applied_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | When the row was persisted |
| `setpoint_delta_f` | `Numeric(5,2)` | NOT NULL | Echoes the underlying recommendation's delta |
| `status` | `String(16)` | NOT NULL, CHECK in (`dispatched`, `failed`) | Outcome from adapter or short-circuit |
| `error_code` | `String(64)` | NULL | One of `adapter_error`, `missing_device`, `already_applied`, or NULL on success |
| `adapter_message` | `String(255)` | NOT NULL, default `''` | Free-form adapter detail |
| `latency_ms` | `Integer` | NOT NULL, default `0` | Adapter-reported latency |

**Indexes:**
- `(building_id, applied_at DESC)` — fast "latest applies for building".

### Reused tables
- `buildings`, `zones`, `devices` — read-only context.
- `setpoint_recommendations` (UC4) — read-only; validation looks up the latest-run rows by `recommendation_id`.

### Migration
New Alembic revision chained off the UC4 head `a91c2f3d7e84` creates the table, the UNIQUE constraint, the CHECK on `status`, the FKs, and the `(building_id, applied_at)` index. No changes to existing tables.

### Reset rules (acceptance)
Truncate list updated to include the new table **before** `setpoint_recommendations` so FKs cascade cleanly:

```
TRUNCATE applied_setpoint_changes, setpoint_recommendations, zone_comfort_constraints,
         demand_forecasts, occupancy_records, operating_schedules, devices, zones,
         buildings RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- Background seeds buildings, zones, occupancy snapshots, weather + device-state doubles, demand forecasts, comfort constraints, and a prior UC4 recommendation run.
- `applied_setpoint_changes` is empty at scenario start.
- The `DeviceControlAdapter` test double is reset (no directives, call log cleared) at the start of every scenario.
- HVAC devices for each zone are auto-created by the existing UC1/UC3 building-seeding step (one `DeviceModel(device_type="HVAC")` per zone). UC5 service uses a case-insensitive match (`lower(device_type) = 'hvac'`).

### Atomicity
The service performs all `applied_setpoint_changes` writes inside a single SQLAlchemy session transaction. On adapter exception → caught and recorded as `failed`/`adapter_error` (still inside the same transaction). On DB error during commit → SQLAlchemy raises, FastAPI handler maps to 500, no rows are visible after rollback.
