# UC10 HandleSensorDataOutage — Structured Requirement

## A) Structured Requirement

**Use case name:** HandleSensorDataOutage

**Participating actors:**
- MonitoringService (primary; internal actor that asserts a sensor outage via a POST to the trigger boundary — A3).
- ForecastingService (secondary; its latest `demand_forecasts` rows are flagged degraded — A2).
- RecommendationService (secondary; its latest-run `setpoint_recommendations` rows are flagged degraded — A2).
- FacilityManager (notification target; can also declare a synthetic outage and review history from `/sensor-outage`).
- SensorOutageEventStore (DB-backed; **new** `sensor_outage_events` table — append-only log).

**Goal:** When the MonitoringService asserts that sensor data is missing/stale for one or more zones of a building, the system records a `sensor_outage_events` row, decides between `fallback` and `paused` per A1, marks the affected forecasts and recommendations with `degraded_confidence=true` (fallback case only), logs the outage, and returns a `SensorOutageResult`. The decision and all flag updates commit in a single transaction (A5). Quality target: server-measured `elapsed_ms < 2000` (A6).

**Preconditions:**
- The target building exists and has at least one zone.
- Every zone id in `affected_zone_ids` belongs to that building.
- `reason` is a non-empty string.

**Trigger boundary:** `POST /api/sensors/outage/handle` body `{"building_id": int, "affected_zone_ids": [int, ...], "reason": str}`.

**Main success flow:**
1. The MonitoringService (or FM via UI) POSTs the handle endpoint with the building id, the list of affected zone ids, and a reason string.
2. The system validates the building exists (else 400 `missingInputs=["building"]`), `affected_zone_ids` is non-empty (else 400 `["affected_zone_ids"]`), every zone id belongs to the building (else 400 `["zone"]`), and `reason` is non-empty (else 400 `["reason"]`). The labels are deduplicated and sorted alphabetically.
3. The system applies the decision rule (A1):
   - If every zone of the building is in `affected_zone_ids` AND no `demand_forecasts` row exists for any of those zones with `created_at >= now() - INTERVAL '24 hours'` → `decision='paused'` (no flag updates; A8).
   - Otherwise → `decision='fallback'`. For each zone in `affected_zone_ids`, set `degraded_confidence=true` on the latest `demand_forecasts` row for that zone (no-op if the zone has no forecast rows). Then set `degraded_confidence=true` on every `setpoint_recommendations` row whose `building_id` matches AND whose `run_timestamp` equals the building's latest `setpoint_recommendations` `run_timestamp` AND whose `zone_id` is in `affected_zone_ids` (A2).
4. The system writes one `sensor_outage_events` row carrying `building_id`, `declared_at=now()`, `affected_zone_ids` (JSON), `reason`, `decision`, `notes` (carrying the reason verbatim; A8 — and an explanatory tail when paused), `elapsed_ms`. Everything commits in one SQLAlchemy transaction (A5).
5. The system emits a stdlib INFO log line describing the outage decision (A4).
6. Return `SensorOutageResult` carrying the event id, `building_id`, `affected_zone_ids`, `decision`, `notes`, `degraded_forecast_zone_ids`, `degraded_recommendation_ids`, `elapsed_ms`, `declared_at`.
7. FacilityManager reviews on `/sensor-outage`; degraded badges appear on `/forecasts` and `/recommendations` for affected zones.

**Success postconditions:**
- Exactly one new `sensor_outage_events` row exists for the request.
- For `decision='fallback'`: for each affected zone with a forecast row, that zone's latest `demand_forecasts` row has `degraded_confidence=true`; for every affected zone whose latest-run `setpoint_recommendations` row exists, those rows have `degraded_confidence=true`. Non-affected zones' rows are unchanged.
- For `decision='paused'`: zero flag updates.

**Failure postconditions:**
- On any `missingInputs` 400: zero new rows in `sensor_outage_events`, no flag updates.
- On a forced mid-write DB error (test lever): the transaction rolls back; event row count + flag state unchanged; 500 response.

**Quality requirements:**
- Q1: Fallback status is explicit in every affected forecast and recommendation row (`degraded_confidence=true`) AND in the `SensorOutageResult` (`decision`, `notes`).
- Q2: Server-measured `elapsed_ms < 2000` (A6).
- Q3: Atomicity — the event row + all flag updates commit together or not at all (A5, S11).

### Numbered Assumptions

- **A1** Decision rule: `decision='paused'` iff `affected_zone_ids` covers every zone of the building AND no `demand_forecasts` row exists for any of those zones with `created_at >= now() - INTERVAL '24 hours'`. Otherwise `decision='fallback'`.
- **A2** "Mark affected forecasts and recommendations": for each zone in `affected_zone_ids`, set `degraded_confidence=true` on the **latest** `demand_forecasts` row for that zone (highest `created_at`; tiebreaker `id`). For recommendations, set `degraded_confidence=true` on every `setpoint_recommendations` row whose `building_id` matches AND whose `run_timestamp` equals the building's latest `setpoint_recommendations.run_timestamp` AND whose `zone_id` is in `affected_zone_ids`. No other rows are touched.
- **A3** Trigger: MonitoringService is an internal actor; the event = the POST body. Real-time background polling is **deferred**.
- **A4** Notification: a stdlib INFO log line (`logger.info("sensor_outage_handled ...")`) is emitted on every success. Real notification channel (email/Slack/page) is **deferred**.
- **A5** Atomicity: the `sensor_outage_events` insert + all `degraded_confidence` UPDATEs commit together in a single SQLAlchemy transaction. On any DB error the transaction rolls back; zero new rows survive (S11).
- **A6** Quality Q2 = `elapsed_ms < 2000` for happy fallback and paused cases.
- **A7** No idempotency: re-declaring an outage for the same zones creates a second `sensor_outage_events` row. Flags already `true` stay `true` (no-op UPDATE on idempotent rows).
- **A8** A `decision='paused'` request still writes a `sensor_outage_events` row with `notes` set to `reason + " | no recent forecast for any zone — planning paused"`. No flag updates are performed.
- **A9** Existing forecasts/recommendations created BEFORE UC10's migration default to `degraded_confidence=false`. The column is added with `DEFAULT FALSE NOT NULL`; existing rows backfill to `false` via the column default.
- **A10** Cross-UC surface change: UC3's `ZoneForecastOut` response model and UC4's `RecommendationOut` response model gain a `degraded_confidence: bool = False` field. Additive only — no breaking change to existing UC3/UC4 acceptance tests. Frontend `/forecasts` and `/recommendations` pages render a `degraded-badge-<zone_id>` element when the flag is true.

## B) Acceptance Checks Table

| Use-case statement | Acceptance check | Covered by |
|---|---|---|
| Happy fallback — one zone affected, recent forecast exists | 200 + decision='fallback' + that zone's latest forecast row + latest-run rec rows flagged | S01 |
| Multi-zone fallback — only affected zones flagged | 200 + only affected zones' rows flagged; unaffected zones untouched | S02 |
| Pause path — all zones affected, no recent forecast | 200 + decision='paused' + no flag updates + event row present with notes | S03 |
| All zones but recent forecast exists for at least one | 200 + decision='fallback' (A1 requires NO recent forecast for ALL zones to pause) | S04 |
| Degraded-confidence persistence — flag survives in DB | DB row degraded_confidence=true on the marked row; older rows for same zone stay false | S05 |
| Re-declare outage is non-idempotent | Two events rows; flags stay true | S06 |
| Unknown building | 400 missingInputs=["building"], zero rows | S07 |
| Empty affected_zone_ids | 400 missingInputs=["affected_zone_ids"] | S08 |
| Unknown zone id (cross-building) | 400 missingInputs=["zone"], zero rows | S09 |
| Missing reason | 400 missingInputs=["reason"] | S10 |
| Atomicity — forced DB error mid-write | 500 + zero new event rows + flag state preserved | S11 |
| Cross-building isolation | run for A doesn't flag building B's rows | S12 |
| Performance — 5-zone elapsed_ms < 2000 | 200 + body.elapsed_ms < 2000 | S13 |
| UC3 forecast response surfaces degraded flag | GET /forecasts/latest carries degraded_confidence per row | S14 |
| UC4 recommendations response surfaces degraded flag | GET /recommendations/latest carries degraded_confidence per row | S15 |
| GET history endpoint | GET /sensor-outages returns events ordered by declared_at DESC | S16 |
| UI flow via /sensor-outage | decision pill + affected zones + notes + history row + degraded badges on /forecasts and /recommendations | S17 |

## C) Acceptance Oracles

- **Persistence oracle:** After a successful 200 response, exactly one new `sensor_outage_events` row exists for the request, carrying the request's `affected_zone_ids` (as JSON) and `decision`.
- **Fallback flag oracle:** When `decision='fallback'`, for each zone in `affected_zone_ids` that has at least one `demand_forecasts` row, the most-recent such row has `degraded_confidence=true`. For each affected zone whose latest-run `setpoint_recommendations` row exists, that row has `degraded_confidence=true`.
- **Pause oracle:** When `decision='paused'`, zero `demand_forecasts` and zero `setpoint_recommendations` rows change `degraded_confidence`; the event row still persists with `decision='paused'` (A8).
- **Isolation oracle:** Flags on non-affected zones AND on every row of other buildings remain `false` (S02, S12).
- **Missing-inputs oracle:** The 400 response carries `detail.missingInputs` drawn from `{building, affected_zone_ids, zone, reason}`, sorted alphabetically and deduplicated.
- **Atomicity oracle:** On a forced 500 mid-write, `sensor_outage_events` row count and `degraded_confidence` distribution are unchanged (S11).
- **Quality oracle Q2:** `body.elapsed_ms < 2000` (S13).
- **UC3 surface oracle:** `GET /api/buildings/{id}/forecasts/latest` returns objects containing `degraded_confidence: bool` per row (S14).
- **UC4 surface oracle:** `GET /api/buildings/{id}/recommendations/latest` returns objects containing `degraded_confidence: bool` per row (S15).
- **History oracle:** `GET /api/buildings/{id}/sensor-outages` returns the events ordered by `declared_at DESC` (S16).
- **UI oracle:** `/sensor-outage` shows `outage-decision-pill`, one `outage-affected-zone-{zone_id}` chip per affected zone, `outage-notes`, and one `outage-history-row-{event_id}` per past event. On `/forecasts` and `/recommendations`, after fallback, a `degraded-badge-{zone_id}` element is visible for each affected zone (S17).

## D) Deferred Scope (Recap)

- Real-time background polling for sensor staleness — UC10 only handles outages asserted via the POST trigger (A3).
- Real notification channel (email/Slack/page) — UC10 only emits a stdlib INFO log line (A4).
- Auto-recovery from outage (clearing `degraded_confidence` when sensors come back online) — re-running the relevant UC3/UC4 flow simply creates new rows with the column default `false`. No explicit clear-outage endpoint.
- Per-zone different decisions in a single outage — UC10 makes one decision per request.
- Per-user authentication / authorization — the handle endpoint is invocable by any caller in the test harness.
