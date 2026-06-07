"""UC7 DetectComfortViolationRisk step definitions.

Reuses background steps from UC1/UC3/UC4 via behave's global step registry.
"""
import time

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


def _activate(context, building_name):
    entry = context.buildings_by_name.get(building_name)
    if entry is None:
        return
    context.building_id = entry["id"]
    context.building_name = building_name
    context.zones = entry["zones"]


def _run_risk(context, building_name):
    bid = _bid(context, building_name)
    _activate(context, building_name)
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/comfort-risk/run",
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = (time.perf_counter() - start) * 1000.0
    return res


def _count_table_for_building(table: str, building_id: int) -> int:
    """Count rows in a comfort-risk table scoped to a building.

    `comfort_risk_alerts` joins via `zone_id → zones.building_id`.
    """
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            if table == "comfort_risk_runs":
                row = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM comfort_risk_runs "
                        "WHERE building_id = :b"
                    ),
                    {"b": building_id},
                ).first()
            elif table == "comfort_risk_alerts":
                row = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM comfort_risk_alerts a "
                        "JOIN zones z ON z.id = a.zone_id "
                        "WHERE z.building_id = :b"
                    ),
                    {"b": building_id},
                ).first()
            else:
                raise AssertionError(f"unknown UC7 table {table!r}")
            return int(row[0]) if row else 0
    finally:
        engine.dispose()


# -- Background extensions ---------------------------------------------------


@given('the DeviceStateAdapter setpoint_f is set to {temp:d} for every zone of "{building_name}"')
def step_seed_setpoint_f_all_zones(context, temp, building_name):
    zones = _zones(context, building_name)
    for zone_id in zones.values():
        httpx.post(
            f"{context.backend_url}/api/_test/forecast_doubles",
            json={
                "kind": "device_state",
                "zone_id": zone_id,
                "payload": {"on_count": 2, "setpoint_f": temp},
            },
            timeout=5.0,
        )


@given('the latest recommendation setpoint_delta_f for zone "{zone_name}" of "{building_name}" is set to {delta}')
def step_set_recommendation_delta(context, zone_name, building_name, delta):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    res = httpx.post(
        f"{context.backend_url}/api/_test/recommendations/set_delta_for_zone",
        json={"zone_id": zone_id, "setpoint_delta_f": float(delta)},
        timeout=5.0,
    )
    assert res.status_code == 200, f"set_delta_for_zone failed: {res.status_code} {res.text}"


@given('the latest recommendation rows for zone "{zone_name}" of "{building_name}" are deleted')
def step_clear_recs_for_zone(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    res = httpx.post(
        f"{context.backend_url}/api/_test/recommendations/clear_for_zone",
        json={"zone_id": zone_id},
        timeout=5.0,
    )
    assert res.status_code == 200, f"clear recs failed: {res.status_code} {res.text}"


@given('the ComfortRiskService is configured to force a DB error on the next run for "{building_name}"')
def step_force_db_error(context, building_name):
    httpx.post(
        f"{context.backend_url}/api/_test/comfort_risk/force_db_error",
        timeout=5.0,
    )


# -- Actions -----------------------------------------------------------------


@when('the Scheduler triggers a comfort-risk run for "{building_name}"')
def step_when_trigger_run(context, building_name):
    _run_risk(context, building_name)


@when('the Scheduler triggers a comfort-risk run for "{building_name}" again')
def step_when_trigger_run_again(context, building_name):
    # Stash the first response before overwriting last_response.
    context.first_response = context.last_response
    res = _run_risk(context, building_name)
    context.second_response = res


@when("the Scheduler triggers a comfort-risk run for an unknown building id")
def step_when_trigger_unknown_building(context):
    res = httpx.post(
        f"{context.backend_url}/api/buildings/9999999/comfort-risk/run",
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = 0.0


@when('the user triggers a comfort-risk run for "{building_name}" via the ComfortRiskPage')
def step_when_ui_run(context, building_name):
    _activate(context, building_name)
    page = context.page
    page.goto(f"{context.frontend_url}/comfort-risk")
    page.wait_for_selector('[data-testid="comfort-risk-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="comfort-risk-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="comfort-risk-building-selector"]', label=building_name
    )
    page.click('[data-testid="comfort-risk-run-button"]')
    page.wait_for_selector(
        '[data-testid="comfort-risk-success-banner"], [data-testid="comfort-risk-error-banner"]',
        timeout=15_000,
    )


# -- Assertions --------------------------------------------------------------


@then('the comfort-risk response has decision "{decision}"')
def step_then_decision(context, decision):
    res = context.last_response
    assert res.status_code == 200, (
        f"expected 200; got {res.status_code}: {res.text}"
    )
    body = res.json()
    assert body["decision"] == decision, (
        f"decision={body['decision']!r} expected {decision!r}"
    )


@then("the comfort-risk response has alerts_count {n:d}")
def step_then_alerts_count(context, n):
    body = context.last_response.json()
    assert body["alerts_count"] == n, (
        f"alerts_count={body['alerts_count']} expected {n}"
    )


def _find_alert(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zid = zones[zone_name]
    body = context.last_response.json()
    for a in body["alerts"]:
        if a["zone_id"] == zid:
            return a
    return None


@then('the comfort-risk alert for zone "{zone_name}" of "{building_name}" has direction "{direction}"')
def step_then_alert_direction(context, zone_name, building_name, direction):
    a = _find_alert(context, zone_name, building_name)
    assert a is not None, f"no alert for zone {zone_name!r}"
    assert a["direction"] == direction, (
        f"direction={a['direction']!r} expected {direction!r}"
    )


@then('the comfort-risk alert for zone "{zone_name}" of "{building_name}" has mitigation "{text}"')
def step_then_alert_mitigation_exact(context, zone_name, building_name, text):
    a = _find_alert(context, zone_name, building_name)
    assert a is not None, f"no alert for zone {zone_name!r}"
    assert a["mitigation"] == text, (
        f"mitigation={a['mitigation']!r} expected {text!r}"
    )


@then('the comfort-risk alert for zone "{zone_name}" of "{building_name}" has mitigation starting with "{prefix}"')
def step_then_alert_mitigation_prefix(context, zone_name, building_name, prefix):
    a = _find_alert(context, zone_name, building_name)
    assert a is not None, f"no alert for zone {zone_name!r}"
    assert a["mitigation"].startswith(prefix), (
        f"mitigation={a['mitigation']!r} does not start with {prefix!r}"
    )


@then('the comfort-risk alert for zone "{zone_name}" of "{building_name}" has risk_score "{score}"')
def step_then_alert_score(context, zone_name, building_name, score):
    a = _find_alert(context, zone_name, building_name)
    assert a is not None, f"no alert for zone {zone_name!r}"
    assert str(a["risk_score"]) == score, (
        f"risk_score={a['risk_score']!r} expected {score!r}"
    )


@then('no comfort-risk alert exists for zone "{zone_name}" of "{building_name}"')
def step_then_no_alert(context, zone_name, building_name):
    a = _find_alert(context, zone_name, building_name)
    assert a is None, f"unexpected alert for zone {zone_name!r}: {a}"


@then('the database contains {n:d} comfort_risk_runs rows for "{building_name}"')
def step_then_db_runs_count(context, n, building_name):
    bid = _bid(context, building_name)
    actual = _count_table_for_building("comfort_risk_runs", bid)
    assert actual == n, f"expected {n} comfort_risk_runs rows; got {actual}"


@then('the database contains {n:d} comfort_risk_alerts rows for "{building_name}"')
def step_then_db_alerts_count(context, n, building_name):
    bid = _bid(context, building_name)
    actual = _count_table_for_building("comfort_risk_alerts", bid)
    assert actual == n, f"expected {n} comfort_risk_alerts rows; got {actual}"


@then('the comfort-risk run is rejected with a missing-inputs error listing "{label}"')
def step_then_missing(context, label):
    res = context.last_response
    assert res.status_code == 400, (
        f"expected 400; got {res.status_code}: {res.text}"
    )
    body = res.json()
    missing = body.get("detail", {}).get("missingInputs", [])
    assert label in missing, f"{label!r} not in missingInputs={missing}"


@then("the comfort-risk run returns a 500 server error")
def step_then_500(context):
    res = context.last_response
    assert res.status_code == 500, (
        f"expected 500; got {res.status_code}: {res.text}"
    )


@then("the comfort-risk run completes in under {limit_ms:d} milliseconds")
def step_then_perf(context, limit_ms):
    body = context.last_response.json()
    assert body.get("elapsed_ms", 0) < limit_ms, (
        f"server elapsed_ms={body.get('elapsed_ms')} exceeds {limit_ms}"
    )
    assert context.last_elapsed_ms < limit_ms, (
        f"client elapsed_ms={context.last_elapsed_ms:.1f} exceeds {limit_ms}"
    )


@then('the two comfort-risk runs produce identical alert rows for "{building_name}"')
def step_then_determinism(context, building_name):
    first = context.first_response.json()
    second = context.second_response.json()
    def _key(a):
        return (a["zone_id"], str(a["risk_score"]), a["direction"], a["mitigation"])
    first_set = sorted([_key(a) for a in first["alerts"]])
    second_set = sorted([_key(a) for a in second["alerts"]])
    assert first_set == second_set, (
        f"determinism violated: first={first_set} second={second_set}"
    )


# -- UI assertions -----------------------------------------------------------


@then("the ComfortRiskPage shows the success banner")
def step_then_ui_success(context):
    context.page.wait_for_selector(
        '[data-testid="comfort-risk-success-banner"]', timeout=5_000
    )


@then('the ComfortRiskPage decision pill reads "{decision}"')
def step_then_ui_pill(context, decision):
    pill = context.page.locator('[data-testid="comfort-risk-decision-pill"]')
    txt = pill.inner_text().strip()
    assert txt == decision, f"pill reads {txt!r}; expected {decision!r}"


@then('the ComfortRiskPage lists zone "{zone_name}" of "{building_name}" as an alert row')
def step_then_ui_alert_row(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zid = zones[zone_name]
    context.page.wait_for_selector(
        f'[data-testid="comfort-risk-alert-row-{zid}"]', timeout=5_000
    )
