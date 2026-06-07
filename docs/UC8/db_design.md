# UC8 ExplainRecommendation — Database Design

## Part B) Database Design Summary

### New table: `recommendation_explanations`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `recommendation_id` | `Integer` | NOT NULL, **UNIQUE**, FK → `setpoint_recommendations.id` ON DELETE CASCADE | UNIQUE enforces UC8 idempotency (A3). |
| `generated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Audit / ordering. |
| `text` | `Text` | NOT NULL | Natural-language explanation string. |
| `factors_json` | `JSON` | NOT NULL | Structured `{energy, comfort, occupancy}` payload (A10). |
| `elapsed_ms` | `Integer` | NOT NULL, default `0` | Server-measured first-generation latency. |
| `model_version` | `String(64)` | NOT NULL | Returned by the adapter. |

**Indexes:**
- `ix_recommendation_explanations_recommendation` on `(recommendation_id)` — fast cache lookup (UNIQUE already implies this on PostgreSQL, but the explicit index keeps the migration self-documenting).

### Reused tables (read-only context)
- `setpoint_recommendations` — recommendation row + `projected_savings_kwh`, `comfort_impact`, `setpoint_delta_f`, `run_timestamp`.
- `zone_comfort_constraints` — comfort band for the recommendation's zone.
- `occupancy_records` — latest snapshot at-or-before the recommendation's `run_timestamp`.
- `demand_forecasts` — the latest forecast row for `zone_id` with `timestamp <= run_timestamp` (matches UC4's freshness lookup).

### Migration
New Alembic revision chained off the UC7 head `f9b3e7a82c41`. File: `backend/alembic/versions/a4c7d2e91b58_uc8_recommendation_explanations.py`. Creates the table, the UNIQUE constraint, the FK, and the index. No changes to existing tables.

### Reset rules (acceptance)
Truncate list extended to **prepend** `recommendation_explanations`:

```
TRUNCATE recommendation_explanations, comfort_risk_alerts, comfort_risk_runs,
         plan_adaptation_events, applied_setpoint_changes, setpoint_recommendations,
         zone_comfort_constraints, demand_forecasts, occupancy_records,
         operating_schedules, devices, zones, buildings RESTART IDENTITY CASCADE;
```

### Seed data (acceptance)
- Background seeds (unchanged from UC4/UC7).
- `recommendation_explanations` is empty at scenario start.

### Atomicity
The service performs the single `recommendation_explanations` insert inside one SQLAlchemy session transaction. On any error the transaction is rolled back; FastAPI returns 500 and zero new rows survive (S14).
