# UC10 HandleSensorDataOutage — UI Design

## Part A — UI Design

### Route

`/sensor-outage` — dual-purpose page (declare outage + review history).

### Page sections

1. **Header**: title "Sensor Data Outage".
2. **Declare panel**:
   - Building selector (`outage-building-selector`).
   - Zone checkbox list (one per zone of the selected building) — `outage-zone-checkbox-{zone_id}`.
   - Reason text input (`outage-reason-input`).
   - Declare button (`outage-declare-button`).
3. **Result banner** (visible after a successful POST):
   - Success banner (`outage-success-banner`).
   - Decision pill (`outage-decision-pill`) — `fallback` or `paused`.
   - One chip per affected zone (`outage-affected-zone-{zone_id}`).
   - Notes paragraph (`outage-notes`).
4. **Error banner** (`outage-error-banner`) + `outage-missing-inputs` span when missingInputs is non-empty.
5. **History table**: rows ordered by `declared_at` DESC. Each row carries `outage-history-row-{event_id}` and inner cells for `declared_at`, `decision`, `reason`, affected zone count.

### Cross-UC additions (A10)

- `/forecasts` page renders `degraded-badge-{zone_id}` next to the predicted-kWh cell when the row's `degraded_confidence` is true.
- `/recommendations` page renders `degraded-badge-{zone_id}` next to the zone-name cell when the row's `degraded_confidence` is true.

### `data-testid` inventory

- `outage-building-selector`
- `outage-zone-checkbox-{zone_id}`
- `outage-reason-input`
- `outage-declare-button`
- `outage-success-banner`
- `outage-error-banner`
- `outage-missing-inputs`
- `outage-decision-pill`
- `outage-affected-zone-{zone_id}`
- `outage-notes`
- `outage-history-row-{event_id}`
- `degraded-badge-{zone_id}` (on `/forecasts` and `/recommendations`)

### Page flow

1. On mount: `GET /api/buildings` → populate selector. Auto-select first.
2. On building change: `GET /api/buildings/{id}/sensor-outages` → populate history table; clear declare-form state.
3. On declare click: `POST /api/sensors/outage/handle` with `{building_id, affected_zone_ids, reason}`.
   - 200 → show success banner, decision pill, affected-zone chips, notes; re-fetch history.
   - 400 → render error banner + missing-inputs span.
   - 5xx → render error banner with the generic server-error string.
