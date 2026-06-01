import time
from datetime import datetime, timedelta

import httpx
from behave import given, when, then
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.models import (
    BuildingModel,
    DeviceModel,
    OccupancyRecordModel,
    ZoneModel,
)


# -- Helpers -----------------------------------------------------------------

def _ensure_buildings_map(context):
    if not hasattr(context, "buildings_by_name") or context.buildings_by_name is None:
        context.buildings_by_name = {}


def _bid(context, building_name):
    """Look up a building id by name, falling back to context.building_id."""
    _ensure_buildings_map(context)
    entry = context.buildings_by_name.get(building_name)
    if entry is not None:
        return entry["id"]
    return getattr(context, "building_id", None)


def _zones(context, building_name):
    _ensure_buildings_map(context)
    entry = context.buildings_by_name.get(building_name)
    if entry is not None:
        return entry["zones"]
    return getattr(context, "zones", {})


def _activate(context, building_name):
    """Set the 'current' building so legacy steps using context.building_id work."""
    _ensure_buildings_map(context)
    entry = context.buildings_by_name.get(building_name)
    if entry is None:
        return
    context.building_id = entry["id"]
    context.building_name = building_name
    context.zones = entry["zones"]


# -- Background --------------------------------------------------------------

@given("the system is initialized for acceptance testing")
def step_init(context):
    # Reset any prior adapter doubles state from a previous scenario
    httpx.post(f"{context.backend_url}/api/_test/forecast_doubles/reset", timeout=5.0)
    context.buildings_by_name = {}


@given('a building "{building_name}" exists with zones')
def step_seed_building_with_zone_table(context, building_name):
    _ensure_buildings_map(context)
    zone_names = [row["zone_name"] for row in context.table]
    engine = create_engine(settings.test_database_url, future=True)
    with Session(engine) as db:
        building = BuildingModel(name=building_name)
        for name in zone_names:
            zone = ZoneModel(name=name)
            zone.devices.append(DeviceModel(device_type="HVAC"))
            building.zones.append(zone)
        db.add(building)
        db.commit()
        db.refresh(building)
        zones_map = {z.name: z.id for z in building.zones}
        context.buildings_by_name[building_name] = {
            "id": building.id,
            "zones": zones_map,
        }
        context.building_id = building.id
        context.building_name = building.name
        context.zones = zones_map
    engine.dispose()


@given('a building "{building_name}" exists with no zones')
def step_seed_building_no_zones(context, building_name):
    _ensure_buildings_map(context)
    engine = create_engine(settings.test_database_url, future=True)
    with Session(engine) as db:
        building = BuildingModel(name=building_name)
        db.add(building)
        db.commit()
        db.refresh(building)
        context.buildings_by_name[building_name] = {
            "id": building.id,
            "zones": {},
        }
        context.building_id = building.id
        context.building_name = building.name
        context.zones = {}
    engine.dispose()


@given('the latest occupancy snapshot is seeded for every zone of "{building_name}"')
def step_seed_occupancy_all_zones(context, building_name):
    zones = _zones(context, building_name)
    engine = create_engine(settings.test_database_url, future=True)
    with Session(engine) as db:
        ts = datetime(2026, 4, 27, 9, 0, 0)
        for zone_name, zone_id in zones.items():
            db.add(
                OccupancyRecordModel(
                    zone_id=zone_id, timestamp=ts, occupancy_count=5
                )
            )
        db.commit()
    engine.dispose()


@given('the WeatherAdapter is seeded with current weather for "{building_name}"')
def step_seed_weather(context, building_name):
    bid = _bid(context, building_name)
    httpx.post(
        f"{context.backend_url}/api/_test/forecast_doubles",
        json={
            "kind": "weather",
            "building_id": bid,
            "payload": {"temp_c": 22.0, "humidity": 0.5},
        },
        timeout=5.0,
    )


@given('the DeviceStateAdapter is seeded with current device state for every zone of "{building_name}"')
def step_seed_device_state_all(context, building_name):
    zones = _zones(context, building_name)
    for zone_id in zones.values():
        httpx.post(
            f"{context.backend_url}/api/_test/forecast_doubles",
            json={
                "kind": "device_state",
                "zone_id": zone_id,
                "payload": {"on_count": 2},
            },
            timeout=5.0,
        )


@given("the ForecastModelAdapter test double returns deterministic predictions")
def step_forecast_model_default(context):
    pass  # double is deterministic by default


# -- Targeted "missing input" setup ------------------------------------------

@given('the latest occupancy snapshot is missing for zone "{zone_name}" of "{building_name}"')
def step_clear_occupancy(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/clear_occupancy_for_zone",
        json={"zone_id": zone_id},
        timeout=5.0,
    )


@given('the WeatherAdapter has no data for "{building_name}"')
def step_clear_weather(context, building_name):
    bid = _bid(context, building_name)
    httpx.post(
        f"{context.backend_url}/api/_test/forecast_doubles/clear",
        json={"kind": "weather", "building_id": bid},
        timeout=5.0,
    )


@given('the DeviceStateAdapter has no data for zone "{zone_name}" of "{building_name}"')
def step_clear_device_state(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/forecast_doubles/clear",
        json={"kind": "device_state", "zone_id": zone_id},
        timeout=5.0,
    )


@given('a previous successful forecast run exists for "{building_name}" with {n:d} forecast rows')
def step_seed_prior_run(context, building_name, n):
    bid = _bid(context, building_name)
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/forecasts/run",
        timeout=15.0,
    )
    assert res.status_code == 200, (
        f"prior-run setup failed: {res.status_code} {res.text}"
    )
    body = res.json()
    assert len(body["forecasts"]) == n, (
        f"prior run produced {len(body['forecasts'])} forecasts; expected {n}"
    )


# -- Action ------------------------------------------------------------------

@when('the Scheduler triggers a forecast run for "{building_name}"')
def step_trigger_forecast(context, building_name):
    bid = _bid(context, building_name)
    _activate(context, building_name)
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/forecasts/run",
        timeout=15.0,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    context.last_response = res
    context.last_elapsed_ms = elapsed_ms


@when("the Scheduler triggers a forecast run for an unknown building id")
def step_trigger_unknown_building(context):
    # Use an id far above any seeded building
    unknown_id = 9_999_999
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{unknown_id}/forecasts/run",
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = 0.0


@when("the predicted_kwh per zone is captured as the baseline")
def step_capture_baseline(context):
    body = context.last_response.json()
    context.kwh_baseline = {
        f["zone_id"]: str(f["predicted_kwh"]) for f in body["forecasts"]
    }


@when('the user triggers a forecast run for "{building_name}" via the ForecastsPage')
def step_ui_trigger_run(context, building_name):
    _activate(context, building_name)
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
    page.click('[data-testid="run-forecast-button"]')
    # Wait until either success or error banner appears
    page.wait_for_selector(
        '[data-testid="forecast-run-success"], [data-testid="forecast-run-error"]',
        timeout=10_000,
    )


# -- Assertions --------------------------------------------------------------

@then("the run result lists {n:d} zone forecasts")
def step_run_lists_n(context, n):
    assert context.last_response.status_code == 200, (
        f"expected 200; got {context.last_response.status_code}: {context.last_response.text}"
    )
    body = context.last_response.json()
    assert len(body["forecasts"]) == n, (
        f"expected {n} forecasts; got {len(body['forecasts'])}"
    )


@then("each zone forecast exposes a non-null timestamp and zone_id")
def step_forecasts_have_fields(context):
    body = context.last_response.json()
    for f in body["forecasts"]:
        assert f.get("timestamp"), f"forecast missing timestamp: {f}"
        assert f.get("zone_id"), f"forecast missing zone_id: {f}"


@then("every zone forecast in the result has a distinct zone_id")
def step_distinct_zone_ids(context):
    body = context.last_response.json()
    zone_ids = [f["zone_id"] for f in body["forecasts"]]
    assert len(set(zone_ids)) == len(zone_ids), (
        f"duplicate zone_ids in forecast result: {zone_ids}"
    )


@then("every zone forecast in the result has a distinct predicted_kwh")
def step_distinct_kwh(context):
    body = context.last_response.json()
    kwh_vals = [str(f["predicted_kwh"]) for f in body["forecasts"]]
    assert len(set(kwh_vals)) == len(kwh_vals), (
        f"duplicate predicted_kwh values in forecast result: {kwh_vals}"
    )


@then("the predicted_kwh per zone matches the baseline exactly")
def step_kwh_matches_baseline(context):
    body = context.last_response.json()
    current = {f["zone_id"]: str(f["predicted_kwh"]) for f in body["forecasts"]}
    assert current == context.kwh_baseline, (
        f"determinism violated: baseline={context.kwh_baseline} current={current}"
    )


@then('the database contains {n:d} demand_forecast rows for "{building_name}"')
def step_db_count(context, n, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/forecasts/latest",
        timeout=5.0,
    )
    assert res.status_code == 200, f"latest endpoint failed: {res.status_code}"
    rows = res.json()
    assert len(rows) == n, f"expected {n} rows; got {len(rows)}"


@then('the database still contains {n:d} demand_forecast rows for "{building_name}" from the prior run')
def step_db_still_count(context, n, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/forecasts/latest",
        timeout=5.0,
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == n, f"expected {n} preserved rows; got {len(rows)}"


@then('the ForecastsPage displays {n:d} forecast rows for "{building_name}"')
def step_ui_rows(context, n, building_name):
    context.page.goto(f"{context.frontend_url}/forecasts")
    context.page.wait_for_selector('[data-testid="forecast-building-selector"]')
    context.page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="forecast-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    context.page.select_option(
        '[data-testid="forecast-building-selector"]', label=building_name
    )
    context.page.wait_for_selector('[data-testid="forecast-table"]', timeout=5_000)
    rows = context.page.locator('[data-testid^="forecast-row-"]')
    assert rows.count() == n, f"expected {n} UI rows; got {rows.count()}"


@then('the ForecastsPage displays no forecast rows for "{building_name}"')
def step_ui_no_rows(context, building_name):
    rows = context.page.locator('[data-testid^="forecast-row-"]')
    assert rows.count() == 0, f"expected 0 UI rows; got {rows.count()}"


@then('the ForecastsPage shows an error banner listing "{label}"')
def step_ui_error_banner(context, label):
    context.page.wait_for_selector(
        '[data-testid="forecast-run-error"]', timeout=5_000
    )
    text = context.page.locator(
        '[data-testid="forecast-missing-inputs"]'
    ).inner_text()
    assert label in text, f"{label!r} not in error banner: {text!r}"


@then('the run is rejected with a missing-inputs error listing "{label}"')
def step_missing_inputs_error(context, label):
    res = context.last_response
    assert res.status_code == 400, (
        f"expected 400; got {res.status_code}: {res.text}"
    )
    body = res.json()
    missing = body.get("detail", {}).get("missingInputs", [])
    assert label in missing, f"{label!r} not in missingInputs={missing}"


@then("every persisted demand_forecast row has a non-null timestamp column")
def step_rows_have_ts(context):
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{context.building_id}/forecasts/latest",
        timeout=5.0,
    )
    rows = res.json()
    assert rows, "no forecast rows persisted"
    for r in rows:
        assert r.get("timestamp"), f"row missing timestamp: {r}"


@then("every persisted demand_forecast row has a zone_id referencing an existing zone")
def step_rows_have_valid_zone(context):
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{context.building_id}/forecasts/latest",
        timeout=5.0,
    )
    rows = res.json()
    valid_zone_ids = set(context.zones.values())
    for r in rows:
        assert r["zone_id"] in valid_zone_ids, (
            f"forecast zone_id {r['zone_id']} not in {valid_zone_ids}"
        )


@then("every persisted demand_forecast row has a non-empty model_version")
def step_rows_have_model_version(context):
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{context.building_id}/forecasts/latest",
        timeout=5.0,
    )
    rows = res.json()
    assert rows, "no forecast rows persisted"
    for r in rows:
        mv = r.get("model_version")
        assert isinstance(mv, str) and mv.strip(), (
            f"row missing/empty model_version: {r}"
        )


@then("the forecast run completes in under {limit_ms:d} milliseconds")
def step_perf(context, limit_ms):
    body = context.last_response.json()
    assert body.get("elapsed_ms", 0) < limit_ms, (
        f"server-reported elapsed_ms={body.get('elapsed_ms')} exceeds {limit_ms}"
    )
    assert context.last_elapsed_ms < limit_ms, (
        f"client-observed elapsed_ms={context.last_elapsed_ms:.1f} exceeds {limit_ms}"
    )
