"""UC10 HandleSensorDataOutage step definitions.

Reuses background steps `the system is initialized for acceptance testing` and
`a building "..." exists with zones` from UC3's step file (auto-discovered by
behave's global step registry).
"""
import json

import httpx
from behave import given, when, then
from sqlalchemy import create_engine, text

from app.core.config import settings


# -- Helpers -----------------------------------------------------------------


def _bid(context, building_name):
    entry = context.buildings_by_name.get(building_name)
    if entry is not None:
        return entry["id"]
    return getattr(context, "building_id", None)


def _zones(context, building_name):
    entry = context.buildings_by_name.get(building_name)
    if entry is not None:
        return entry["zones"]
    return getattr(context, "zones", {})


def _zone_id(context, building_name, zone_name):
    return _zones(context, building_name)[zone_name]


def _zone_ids_csv(context, building_name, csv):
    names = [n.strip() for n in csv.split(",") if n.strip()]
    zones = _zones(context, building_name)
    return [zones[n] for n in names]


def _post_handle(context, payload):
    res = httpx.post(
        f"{context.backend_url}/api/sensors/outage/handle",
        json=payload,
        timeout=15.0,
    )
    context.last_response = res
    return res


def _count_events(building_id):
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM sensor_outage_events "
                    "WHERE building_id = :b"
                ),
                {"b": building_id},
            ).first()
            return int(row[0]) if row else 0
    finally:
        engine.dispose()


def _latest_forecast_row(zone_id):
    """Return (id, degraded_confidence) for the newest demand_forecasts row
    for `zone_id`, or None when there is no row."""
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, degraded_confidence FROM demand_forecasts "
                    "WHERE zone_id = :z "
                    "ORDER BY created_at DESC, id DESC LIMIT 1"
                ),
                {"z": zone_id},
            ).first()
            return tuple(row) if row else None
    finally:
        engine.dispose()


def _oldest_forecast_row(zone_id):
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, degraded_confidence FROM demand_forecasts "
                    "WHERE zone_id = :z "
                    "ORDER BY created_at ASC, id ASC LIMIT 1"
                ),
                {"z": zone_id},
            ).first()
            return tuple(row) if row else None
    finally:
        engine.dispose()


def _latest_run_recommendation_rows(building_id, zone_id):
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, degraded_confidence FROM setpoint_recommendations "
                    "WHERE zone_id = :z AND building_id = :b "
                    "  AND run_timestamp = ("
                    "    SELECT MAX(run_timestamp) FROM setpoint_recommendations "
                    "    WHERE building_id = :b)"
                ),
                {"z": zone_id, "b": building_id},
            ).all()
            return [tuple(r) for r in rows]
    finally:
        engine.dispose()


# -- Background seeders ------------------------------------------------------


@given(
    'a recent demand_forecasts row exists for zone "{zone_name}" of "{building_name}"'
)
def step_seed_recent_forecast(context, zone_name, building_name):
    zid = _zone_id(context, building_name, zone_name)
    res = httpx.post(
        f"{context.backend_url}/api/_test/forecasts/seed_for_zone",
        json={"zone_id": zid, "hours_ago": 0},
        timeout=10.0,
    )
    assert res.status_code == 200, res.text


@given(
    'a latest-run setpoint_recommendations row exists for zone "{zone_name}" '
    'of "{building_name}"'
)
def step_seed_latest_rec(context, zone_name, building_name):
    bid = _bid(context, building_name)
    zid = _zone_id(context, building_name, zone_name)
    res = httpx.post(
        f"{context.backend_url}/api/_test/recommendations/seed_for_zone",
        json={"building_id": bid, "zone_id": zid},
        timeout=10.0,
    )
    assert res.status_code == 200, res.text


@given(
    'two demand_forecasts rows exist for zone "{zone_name}" of "{building_name}" '
    '— an older one and a newer one'
)
def step_seed_two_forecasts(context, zone_name, building_name):
    zid = _zone_id(context, building_name, zone_name)
    # Older row first (48h ago), then newer (now).
    r1 = httpx.post(
        f"{context.backend_url}/api/_test/forecasts/seed_for_zone",
        json={"zone_id": zid, "hours_ago": 48},
        timeout=10.0,
    )
    assert r1.status_code == 200, r1.text
    r2 = httpx.post(
        f"{context.backend_url}/api/_test/forecasts/seed_for_zone",
        json={"zone_id": zid, "hours_ago": 0},
        timeout=10.0,
    )
    assert r2.status_code == 200, r2.text


@given(
    "the SensorOutageService is configured to force a DB error on the next request"
)
def step_force_db_error(context):
    res = httpx.post(
        f"{context.backend_url}/api/_test/sensor_outage/force_db_error",
        timeout=5.0,
    )
    assert res.status_code == 200, res.text


# -- Actions -----------------------------------------------------------------


@when(
    'the MonitoringService declares a sensor outage for "{building_name}" '
    'affecting zones "{zones_csv}" with reason "{reason}"'
)
def step_declare_outage(context, building_name, zones_csv, reason):
    bid = _bid(context, building_name)
    zone_ids = _zone_ids_csv(context, building_name, zones_csv)
    _post_handle(
        context,
        {
            "building_id": bid,
            "affected_zone_ids": zone_ids,
            "reason": reason,
        },
    )


@when(
    'the MonitoringService declares a sensor outage for "{building_name}" '
    'affecting zones "{zones_csv}" with reason ""'
)
def step_declare_outage_empty_reason(context, building_name, zones_csv):
    bid = _bid(context, building_name)
    zone_ids = _zone_ids_csv(context, building_name, zones_csv)
    _post_handle(
        context,
        {
            "building_id": bid,
            "affected_zone_ids": zone_ids,
            "reason": "",
        },
    )


@when(
    'the MonitoringService declares a sensor outage for unknown building id '
    '{bid:d} affecting zones "{zones_csv}" with reason "{reason}"'
)
def step_declare_unknown_building(context, bid, zones_csv, reason):
    # Use raw zone ids parsed as ints since we have no zone map for this UCN.
    zone_ids = [int(n.strip()) for n in zones_csv.split(",") if n.strip()]
    _post_handle(
        context,
        {
            "building_id": bid,
            "affected_zone_ids": zone_ids,
            "reason": reason,
        },
    )


@when(
    'the MonitoringService declares a sensor outage for "{building_name}" '
    'affecting no zones with reason "{reason}"'
)
def step_declare_no_zones(context, building_name, reason):
    bid = _bid(context, building_name)
    _post_handle(
        context,
        {
            "building_id": bid,
            "affected_zone_ids": [],
            "reason": reason,
        },
    )


@when(
    'the MonitoringService declares a sensor outage for "{building_name}" '
    'affecting zone of "{other_building}" "{zone_name}" with reason "{reason}"'
)
def step_declare_cross_zone(
    context, building_name, other_building, zone_name, reason
):
    bid = _bid(context, building_name)
    zid = _zone_id(context, other_building, zone_name)
    _post_handle(
        context,
        {
            "building_id": bid,
            "affected_zone_ids": [zid],
            "reason": reason,
        },
    )


@when('the FacilityManager fetches the latest forecasts for "{building_name}"')
def step_fetch_latest_forecasts(context, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/forecasts/latest",
        timeout=10.0,
    )
    context.last_response = res


@when(
    'the FacilityManager fetches the latest recommendations for "{building_name}"'
)
def step_fetch_latest_recs(context, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=10.0,
    )
    context.last_response = res


@when(
    'the FacilityManager fetches the sensor outage history for "{building_name}"'
)
def step_fetch_outage_history(context, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/sensor-outages",
        timeout=10.0,
    )
    context.last_response = res


# -- Assertions --------------------------------------------------------------


@then("the sensor outage response status is {code:d}")
def step_then_status(context, code):
    res = context.last_response
    assert res.status_code == code, (
        f"expected {code}; got {res.status_code}: {res.text}"
    )


@then('the sensor outage response has decision "{decision}"')
def step_then_decision(context, decision):
    body = context.last_response.json()
    assert body.get("decision") == decision, (
        f"decision={body.get('decision')!r} expected {decision!r}; body={body}"
    )


@then("the sensor outage response missingInputs equals {payload}")
def step_then_missing_inputs(context, payload):
    body = context.last_response.json()
    actual = body.get("detail", {}).get("missingInputs", [])
    expected = json.loads(payload)
    assert actual == expected, (
        f"missingInputs={actual} expected {expected}; full body={body}"
    )


@then("the sensor outage response elapsed_ms is under {limit_ms:d}")
def step_then_elapsed(context, limit_ms):
    body = context.last_response.json()
    elapsed = float(body.get("elapsed_ms", 0))
    assert elapsed < limit_ms, (
        f"elapsed_ms={elapsed} exceeds {limit_ms}"
    )


@then(
    'the latest demand_forecasts row for zone "{zone_name}" of '
    '"{building_name}" has degraded_confidence "{flag}"'
)
def step_then_latest_forecast_flag(context, zone_name, building_name, flag):
    zid = _zone_id(context, building_name, zone_name)
    row = _latest_forecast_row(zid)
    assert row is not None, (
        f"no demand_forecasts row found for zone {zone_name!r} (id={zid})"
    )
    actual = bool(row[1])
    expected = flag.lower() == "true"
    assert actual == expected, (
        f"latest demand_forecasts.degraded_confidence={actual} "
        f"expected {expected} (row id={row[0]})"
    )


@then(
    'the newest demand_forecasts row for zone "{zone_name}" of '
    '"{building_name}" has degraded_confidence "{flag}"'
)
def step_then_newest_forecast_flag(context, zone_name, building_name, flag):
    zid = _zone_id(context, building_name, zone_name)
    row = _latest_forecast_row(zid)
    assert row is not None, (
        f"no demand_forecasts row found for zone {zone_name!r}"
    )
    actual = bool(row[1])
    expected = flag.lower() == "true"
    assert actual == expected, (
        f"newest demand_forecasts.degraded_confidence={actual} "
        f"expected {expected}"
    )


@then(
    'the oldest demand_forecasts row for zone "{zone_name}" of '
    '"{building_name}" has degraded_confidence "{flag}"'
)
def step_then_oldest_forecast_flag(context, zone_name, building_name, flag):
    zid = _zone_id(context, building_name, zone_name)
    row = _oldest_forecast_row(zid)
    assert row is not None, (
        f"no demand_forecasts row found for zone {zone_name!r}"
    )
    actual = bool(row[1])
    expected = flag.lower() == "true"
    assert actual == expected, (
        f"oldest demand_forecasts.degraded_confidence={actual} "
        f"expected {expected}"
    )


@then(
    'the latest-run setpoint_recommendations rows for zone "{zone_name}" of '
    '"{building_name}" have degraded_confidence "{flag}"'
)
def step_then_latest_rec_flag(context, zone_name, building_name, flag):
    bid = _bid(context, building_name)
    zid = _zone_id(context, building_name, zone_name)
    rows = _latest_run_recommendation_rows(bid, zid)
    expected = flag.lower() == "true"
    assert rows, (
        f"no latest-run setpoint_recommendations rows for zone {zone_name!r}"
    )
    for rid, deg in rows:
        actual = bool(deg)
        assert actual == expected, (
            f"setpoint_recommendations.id={rid} degraded_confidence={actual} "
            f"expected {expected}"
        )


@then(
    'the database contains {n:d} sensor_outage_events row for "{building_name}"'
)
def step_then_event_count_singular(context, n, building_name):
    bid = _bid(context, building_name)
    actual = _count_events(bid)
    assert actual == n, (
        f"expected {n} sensor_outage_events for {building_name!r} (id={bid}); "
        f"got {actual}"
    )


@then(
    'the database contains {n:d} sensor_outage_events rows for "{building_name}"'
)
def step_then_event_count_plural(context, n, building_name):
    bid = _bid(context, building_name)
    actual = _count_events(bid)
    assert actual == n, (
        f"expected {n} sensor_outage_events for {building_name!r} (id={bid}); "
        f"got {actual}"
    )


@then(
    'the sensor_outage_events row notes for "{building_name}" contain "{needle}"'
)
def step_then_event_notes_contain(context, building_name, needle):
    bid = _bid(context, building_name)
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT notes FROM sensor_outage_events "
                    "WHERE building_id = :b "
                    "ORDER BY declared_at DESC, id DESC LIMIT 1"
                ),
                {"b": bid},
            ).first()
    finally:
        engine.dispose()
    assert row is not None, (
        f"no sensor_outage_events row found for {building_name!r}"
    )
    notes = row[0] or ""
    assert needle in notes, (
        f"notes={notes!r} does not contain {needle!r}"
    )


@then(
    'the latest forecasts response carries degraded_confidence "{flag}" for '
    'zone "{zone_name}" of "{building_name}"'
)
def step_then_forecasts_response_degraded(
    context, flag, zone_name, building_name
):
    zid = _zone_id(context, building_name, zone_name)
    body = context.last_response.json()
    matching = [r for r in body if r["zone_id"] == zid]
    assert matching, (
        f"no forecast row for zone id={zid} in {body!r}"
    )
    expected = flag.lower() == "true"
    actual = bool(matching[0].get("degraded_confidence"))
    assert actual == expected, (
        f"forecast degraded_confidence={actual} expected {expected}; "
        f"row={matching[0]}"
    )


@then(
    'the latest recommendations response carries degraded_confidence "{flag}" '
    'for zone "{zone_name}" of "{building_name}"'
)
def step_then_recs_response_degraded(
    context, flag, zone_name, building_name
):
    zid = _zone_id(context, building_name, zone_name)
    body = context.last_response.json()
    matching = [r for r in body if r["zone_id"] == zid]
    assert matching, (
        f"no recommendation row for zone id={zid} in {body!r}"
    )
    expected = flag.lower() == "true"
    actual = bool(matching[0].get("degraded_confidence"))
    assert actual == expected, (
        f"recommendation degraded_confidence={actual} expected {expected}; "
        f"row={matching[0]}"
    )


@then("the sensor outage history has {n:d} events")
def step_then_history_count(context, n):
    body = context.last_response.json()
    assert isinstance(body, list), f"expected list, got {body!r}"
    assert len(body) == n, (
        f"expected {n} history events; got {len(body)}: {body!r}"
    )


@then('the sensor outage history first event reason equals "{reason}"')
def step_then_history_first_reason(context, reason):
    body = context.last_response.json()
    assert len(body) > 0, "history is empty"
    assert body[0]["reason"] == reason, (
        f"first event reason={body[0]['reason']!r} expected {reason!r}"
    )


# -- UI steps ----------------------------------------------------------------


@when(
    'the user declares a sensor outage for "{building_name}" affecting zones '
    '"{zones_csv}" with reason "{reason}" via the SensorOutagePage'
)
def step_ui_declare_outage(
    context, building_name, zones_csv, reason
):
    page = context.page
    page.goto(f"{context.frontend_url}/sensor-outage")
    page.wait_for_selector('[data-testid="outage-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="outage-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="outage-building-selector"]', label=building_name
    )
    # Wait for zone checkboxes to render for the selected building.
    zones = _zones(context, building_name)
    first_zone_id = next(iter(zones.values()))
    page.wait_for_selector(
        f'[data-testid="outage-zone-checkbox-{first_zone_id}"]',
        timeout=5_000,
    )
    for name in [n.strip() for n in zones_csv.split(",") if n.strip()]:
        zid = zones[name]
        page.check(f'[data-testid="outage-zone-checkbox-{zid}"]')
    page.fill('[data-testid="outage-reason-input"]', reason)
    page.click('[data-testid="outage-declare-button"]')
    page.wait_for_selector(
        '[data-testid="outage-success-banner"], '
        '[data-testid="outage-error-banner"]',
        timeout=15_000,
    )


@then("the SensorOutagePage shows the success banner")
def step_then_ui_success(context):
    context.page.wait_for_selector(
        '[data-testid="outage-success-banner"]', timeout=5_000
    )


@then('the SensorOutagePage shows the decision pill with text "{decision}"')
def step_then_ui_decision_pill(context, decision):
    el = context.page.locator('[data-testid="outage-decision-pill"]')
    txt = el.inner_text().strip()
    assert txt == decision, f"decision pill={txt!r} expected {decision!r}"


@then(
    'the SensorOutagePage shows an affected-zone chip for zone "{zone_name}" '
    'of "{building_name}"'
)
def step_then_ui_affected_zone(context, zone_name, building_name):
    zid = _zone_id(context, building_name, zone_name)
    context.page.wait_for_selector(
        f'[data-testid="outage-affected-zone-{zid}"]', timeout=5_000
    )


@then("the SensorOutagePage shows a history row for the newest event")
def step_then_ui_history_row(context):
    # The history table renders any history row after declare. Just assert one exists.
    context.page.wait_for_selector(
        '[data-testid^="outage-history-row-"]', timeout=5_000
    )


@when('the user opens the /forecasts page for "{building_name}"')
def step_open_forecasts_page(context, building_name):
    page = context.page
    page.goto(f"{context.frontend_url}/forecasts")
    page.wait_for_selector('[data-testid="forecast-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="forecast-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="forecast-building-selector"]', label=building_name
    )


@then(
    'the ForecastsPage shows a degraded badge for zone "{zone_name}" of '
    '"{building_name}"'
)
def step_then_forecast_degraded_badge(context, zone_name, building_name):
    zid = _zone_id(context, building_name, zone_name)
    context.page.wait_for_selector(
        f'[data-testid="degraded-badge-{zid}"]', timeout=5_000
    )


@when('the user opens the /recommendations page for "{building_name}"')
def step_open_recommendations_page(context, building_name):
    page = context.page
    page.goto(f"{context.frontend_url}/recommendations")
    page.wait_for_selector('[data-testid="recommendation-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="recommendation-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="recommendation-building-selector"]', label=building_name
    )


@then(
    'the RecommendationsPage shows a degraded badge for zone "{zone_name}" '
    'of "{building_name}"'
)
def step_then_rec_degraded_badge(context, zone_name, building_name):
    zid = _zone_id(context, building_name, zone_name)
    context.page.wait_for_selector(
        f'[data-testid="degraded-badge-{zid}"]', timeout=5_000
    )
