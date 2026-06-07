# UC10 HandleSensorDataOutage — DB Design

## Part B — DB Design

### New table

```
sensor_outage_events (
  id                SERIAL PRIMARY KEY,
  building_id       INT NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  declared_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  affected_zone_ids JSON NOT NULL DEFAULT '[]',
  reason            TEXT NOT NULL DEFAULT '',
  decision          VARCHAR(16) NOT NULL
                    CHECK (decision IN ('fallback','paused')),
  notes             TEXT NOT NULL DEFAULT '',
  elapsed_ms        INT NOT NULL DEFAULT 0
);

CREATE INDEX ix_sensor_outage_events_building_declared
  ON sensor_outage_events (building_id, declared_at DESC);
```

### Schema diffs on existing tables

```
ALTER TABLE demand_forecasts
  ADD COLUMN degraded_confidence BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE setpoint_recommendations
  ADD COLUMN degraded_confidence BOOLEAN NOT NULL DEFAULT FALSE;
```

Existing rows backfill to `false` via the column default (A9).

### Alembic revision

- File: `backend/alembic/versions/<rev>_uc10_sensor_outage.py`
- `revision = "..."` (new id), `down_revision = "b6e3f8a04c19"` (UC9 head).
- `upgrade()` runs the CREATE TABLE + two ALTER TABLE statements.
- `downgrade()` drops the index, the table, then drops the two columns.

### Truncate order (test reset)

Extend `database_reset.py` to truncate `sensor_outage_events` **first** in the comma-separated list, so the table is wiped before its parent `buildings`. The two new columns on existing tables don't need truncation — they're inherent to those tables.

### Indices

- `ix_sensor_outage_events_building_declared (building_id, declared_at DESC)` — supports the history GET.

### Quality

- The `decision` CHECK constraint enforces the closed set `{fallback, paused}` at the DB level.
- `affected_zone_ids` is `JSON NOT NULL DEFAULT '[]'` so empty-list inserts are explicit.
