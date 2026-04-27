# UC3 ForecastZoneDemand — Database Design

## Part B) Database Design Summary

### New table: `demand_forecasts`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `zone_id` | `Integer` | NOT NULL, FK → `zones.id` ON DELETE CASCADE | |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL | The "as-of" time the forecast represents (the run timestamp) |
| `predicted_kwh` | `Numeric(10, 3)` | NOT NULL, CHECK ≥ 0 | Forecast value |
| `model_version` | `String(64)` | NOT NULL | Captured from the adapter at forecast time (A7) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Insertion time (may equal `timestamp` for tests) |

**Index:** `(zone_id, timestamp DESC)` for fast "latest forecast per zone" lookups.

### Reused tables (UC1 + UC2)
- `buildings` — building selector source.
- `zones` — looked up by `building_id`; provides the iteration domain for a forecast run.
- `occupancy_records` — read by the service to validate "latest occupancy snapshot per zone exists" (precondition check; not directly written by UC3).

### Migration
New Alembic revision adds `demand_forecasts` table and the `(zone_id, timestamp DESC)` index. No changes to existing tables.

### Reset rules (acceptance)
The acceptance database reset (`tests/acceptance/support/database_reset.py`) must add `demand_forecasts` to its truncate list **before** `zones` (or rely on `RESTART IDENTITY CASCADE` ordering).

Updated truncate command:
```
TRUNCATE demand_forecasts, occupancy_records, operating_schedules, devices, zones, buildings RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- `Background` step seeds one building "Tower-A" with three zones (Lobby, Floor-1, Floor-2).
- Per scenario, the latest occupancy snapshot is inserted into `occupancy_records` for each zone unless the scenario explicitly omits one (UC3-S02).
- `WeatherAdapter` and `DeviceStateAdapter` test doubles are seeded in-process — no DB tables for them.
- Prior-forecast preservation scenario (UC3-S07) inserts three `demand_forecasts` rows directly via the test harness before triggering the failing run.

### Atomicity
The service performs all writes inside a single SQLAlchemy session/transaction. If validation/adapter checks fail before commit, the session rolls back — no partial rows.
