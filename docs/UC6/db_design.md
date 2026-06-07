# UC6 AdaptPlanToOccupancyChange — Database Design

## Part B) Database Design Summary

### New table: `plan_adaptation_events`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `building_id` | `Integer` | NOT NULL, FK -> `buildings.id` ON DELETE CASCADE | |
| `requested_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Audit trail / ordering key |
| `decision` | `String(16)` | NOT NULL, CHECK in (`replanned`, `no_replan`) | Outcome of the materiality test |
| `reason` | `Text` | NOT NULL, default `''` | Human-readable reason ("material occupancy delta" / "no material change") |
| `active_plan_run_timestamp` | `TIMESTAMPTZ` | NOT NULL | The `run_timestamp` of the plan that was active when the adapt fired |
| `new_run_timestamp` | `TIMESTAMPTZ` | NULL | NULL on `no_replan`; the new run's `run_timestamp` on `replanned` |
| `changed_zone_ids` | `JSON` | NOT NULL, default `'[]'` | Material zones (subset of payload) |
| `elapsed_ms` | `Integer` | NOT NULL, default `0` | Server-reported elapsed time |

**Indexes:**
- `(building_id, requested_at DESC)` — fast "latest events for building" lookups.

### Reused tables
- `buildings`, `zones` — read-only context.
- `occupancy_records` — read for baseline lookup, write for the new event per zone in the payload.
- `setpoint_recommendations` — read to resolve the active plan (latest `run_timestamp` ordered DESC); write a new run when `decision='replanned'` via the reused UC4 service.
- `applied_setpoint_changes` — read-only; qualifies a `setpoint_recommendations` run as the **active plan** when ≥1 row references that run's ids (any `status`).

### Migration
New Alembic revision `e8a5c4d62a7f_uc6_plan_adaptation_events.py` chained off the UC5 head `c7d2a1f9e5b0`. Creates the table, the CHECK on `decision`, the FK on `building_id`, and the `(building_id, requested_at DESC)` index. No changes to existing tables.

### Reset rules (acceptance)
Truncate list extended to include `plan_adaptation_events` **before** `setpoint_recommendations` so FKs cascade cleanly:

```
TRUNCATE plan_adaptation_events, applied_setpoint_changes,
         setpoint_recommendations, zone_comfort_constraints,
         demand_forecasts, occupancy_records, operating_schedules,
         devices, zones, buildings RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- Background seeds the building tree, occupancy snapshots, weather + device-state doubles, demand forecasts, comfort constraints, a prior UC4 recommendation run, and one applied row (the FM "has applied the rank 1 recommendation") so the active-plan precondition is satisfied.
- `plan_adaptation_events` is empty at scenario start.

### Atomicity
The service performs all writes — the new `occupancy_records` rows, the optional new `setpoint_recommendations` run (via `RecommendationService.run_within(commit=False)`), and the `plan_adaptation_events` row — inside a **single SQLAlchemy session transaction**. On any error the transaction is rolled back; FastAPI returns 500 and zero new rows survive.
