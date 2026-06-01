# UC4 RecommendHVACSetpointChanges — Database Design

## Part B) Database Design Summary

### New table: `zone_comfort_constraints`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `zone_id` | `Integer` | PK, FK -> `zones.id` ON DELETE CASCADE | One row per zone |
| `min_setpoint_f` | `Numeric(5,2)` | NOT NULL | Hard lower bound (°F) |
| `max_setpoint_f` | `Numeric(5,2)` | NOT NULL | Hard upper bound (°F) |
| `occupied_min_f` | `Numeric(5,2)` | NOT NULL | Comfort band during occupied hours |
| `occupied_max_f` | `Numeric(5,2)` | NOT NULL | Comfort band during occupied hours |
| `unoccupied_min_f` | `Numeric(5,2)` | NOT NULL | Comfort band during unoccupied hours |
| `unoccupied_max_f` | `Numeric(5,2)` | NOT NULL | Comfort band during unoccupied hours |

### New table: `setpoint_recommendations`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `building_id` | `Integer` | NOT NULL, FK -> `buildings.id` ON DELETE CASCADE | |
| `zone_id` | `Integer` | NOT NULL, FK -> `zones.id` ON DELETE CASCADE | |
| `run_timestamp` | `TIMESTAMPTZ` | NOT NULL | All rows from one run share this timestamp |
| `setpoint_delta_f` | `Numeric(5,2)` | NOT NULL | Suggested change in °F (signed) |
| `projected_savings_kwh` | `Numeric(10,3)` | NOT NULL, CHECK >= 0 | |
| `comfort_impact` | `String(16)` | NOT NULL, CHECK in ('none','minor','moderate') | |
| `rank` | `Integer` | NOT NULL, CHECK >= 1 | Rank within the run (1 = best) |
| `model_version` | `String(64)` | NOT NULL | Adapter-reported model version |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Indexes:**
- `(building_id, run_timestamp DESC)` — fast "latest run for building".
- `(building_id, run_timestamp, rank)` — fast in-order retrieval.

### Reused tables
- `buildings`, `zones` — read-only context for the run.
- `demand_forecasts` (UC3) — read-only; latest row per zone is consumed by the service.

### Migration
New Alembic revision (chained off current head `b4e9c1a07f23`) creates both tables and indexes. No changes to existing tables.

### Reset rules (acceptance)
Truncate list updated to include the two new tables (truncated **before** `zones` / `buildings` so FKs cascade cleanly, although `CASCADE` makes the explicit order moot):

```
TRUNCATE setpoint_recommendations, zone_comfort_constraints, demand_forecasts,
         occupancy_records, operating_schedules, devices, zones, buildings
         RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- Background seeds `zone_comfort_constraints` per zone via a test-only control endpoint (`POST /api/_test/comfort_constraints/seed`). Default values:
  - `min_setpoint_f = 65.0`, `max_setpoint_f = 78.0`
  - `occupied_min_f = 68.0`, `occupied_max_f = 75.0`
  - `unoccupied_min_f = 65.0`, `unoccupied_max_f = 78.0`
  - Midpoint (baseline for feasibility filter) = 71.5 °F.
- Background seeds a fresh `demand_forecasts` row per zone (current timestamp) by reusing the UC3 trigger endpoint.
- `setpoint_recommendations` is otherwise empty at scenario start.

### Atomicity
The service performs all `setpoint_recommendations` writes inside a single SQLAlchemy session transaction. Validation/staleness/feasibility checks all run before any write; on `RecommendationInputsMissing`, the session is not committed.
