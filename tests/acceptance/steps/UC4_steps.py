"""UC4 RecommendHVACSetpointChanges step definitions.

Reuses building/occupancy/forecast steps from UC3_steps.py via behave's global
step registry (which loads every *_steps.py file).
"""
import time

import httpx
from behave import given, when, then


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


# -- Background extensions ---------------------------------------------------


@given('a fresh demand forecast exists for every zone of "{building_name}"')
def step_seed_fresh_forecast(context, building_name):
    bid = _bid(context, building_name)
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/forecasts/run",
        timeout=15.0,
    )
    assert res.status_code == 200, (
        f"forecast seed failed: {res.status_code} {res.text}"
    )


@given('default comfort constraints are seeded for every zone of "{building_name}"')
def step_seed_default_constraints(context, building_name):
    zones = _zones(context, building_name)
    for zone_id in zones.values():
        res = httpx.post(
            f"{context.backend_url}/api/_test/comfort_constraints/seed",
            json={"zone_id": zone_id},
            timeout=5.0,
        )
        assert res.status_code == 200, (
            f"seed constraints failed: {res.status_code} {res.text}"
        )


@given("the OptimizationAdapter test double returns deterministic recommendations")
def step_reset_opt_double(context):
    httpx.post(
        f"{context.backend_url}/api/_test/optimization_double/reset",
        timeout=5.0,
    )


@given(
    'the OptimizationAdapter test double is configured to emit an '
    'infeasible candidate for zone "{zone_name}" of "{building_name}"'
)
def step_force_infeasible(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/optimization_double/force_infeasible",
        json={"zone_id": zone_id},
        timeout=5.0,
    )


@given('the latest demand forecast is missing for zone "{zone_name}" of "{building_name}"')
def step_clear_forecast_for_zone(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/forecasts/clear_for_zone",
        json={"zone_id": zone_id},
        timeout=5.0,
    )


@given(
    'the latest demand forecast for zone "{zone_name}" of "{building_name}" '
    'is forced to {hours:d} hours old'
)
def step_force_stale_forecast(context, zone_name, building_name, hours):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/forecasts/force_stale",
        json={"zone_id": zone_id, "hours_old": hours},
        timeout=5.0,
    )


@given('the comfort constraints for zone "{zone_name}" of "{building_name}" are deleted')
def step_delete_constraints(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/comfort_constraints/clear",
        json={"zone_id": zone_id},
        timeout=5.0,
    )


@given(
    'a previous successful recommendation run exists for "{building_name}" '
    'with {n:d} recommendation rows'
)
def step_seed_prior_rec_run(context, building_name, n):
    bid = _bid(context, building_name)
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/run",
        timeout=15.0,
    )
    assert res.status_code == 200, (
        f"prior recommendation run failed: {res.status_code} {res.text}"
    )
    body = res.json()
    assert len(body["recommendations"]) == n, (
        f"prior rec run produced {len(body['recommendations'])} rows; expected {n}"
    )


# -- Actions -----------------------------------------------------------------


@when('the FacilityManager triggers a recommendation run for "{building_name}"')
def step_trigger_rec_run(context, building_name):
    bid = _bid(context, building_name)
    _activate(context, building_name)
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/run",
        timeout=15.0,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    context.last_response = res
    context.last_elapsed_ms = elapsed_ms


@when("the FacilityManager triggers a recommendation run for an unknown building id")
def step_trigger_rec_run_unknown(context):
    res = httpx.post(
        f"{context.backend_url}/api/buildings/9999999/recommendations/run",
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = 0.0


@when("the ranked recommendations are captured as the baseline")
def step_capture_baseline_recs(context):
    body = context.last_response.json()
    context.rec_baseline = [
        (
            r["zone_id"],
            str(r["setpoint_delta_f"]),
            str(r["projected_savings_kwh"]),
            r["comfort_impact"],
            r["rank"],
        )
        for r in body["recommendations"]
    ]


@when('the user triggers a recommendation run for "{building_name}" via the RecommendationsPage')
def step_ui_trigger_rec_run(context, building_name):
    _activate(context, building_name)
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
    page.click('[data-testid="recommendation-run-button"]')
    page.wait_for_selector(
        '[data-testid="recommendation-run-success"], [data-testid="recommendation-run-error"]',
        timeout=10_000,
    )


# -- Assertions --------------------------------------------------------------


@then("the run result lists {n:d} recommendation rows")
def step_assert_rec_count(context, n):
    res = context.last_response
    assert res.status_code == 200, f"expected 200; got {res.status_code}: {res.text}"
    body = res.json()
    assert len(body["recommendations"]) == n, (
        f"expected {n} recs; got {len(body['recommendations'])}"
    )


@then(
    "each recommendation row exposes building_id, zone_id, setpoint_delta_f, "
    "projected_savings_kwh, comfort_impact, rank, and model_version"
)
def step_assert_rec_fields(context):
    body = context.last_response.json()
    required = {
        "building_id",
        "zone_id",
        "setpoint_delta_f",
        "projected_savings_kwh",
        "comfort_impact",
        "rank",
        "model_version",
    }
    for r in body["recommendations"]:
        missing = required - r.keys()
        assert not missing, f"row missing fields {missing}: {r}"
        for f in required:
            assert r[f] is not None, f"field {f} is null in row {r}"


@then('the database contains {n:d} setpoint_recommendation rows for "{building_name}"')
def step_assert_db_rec_count(context, n, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    )
    assert res.status_code == 200, f"latest endpoint failed: {res.status_code}"
    rows = res.json()
    assert len(rows) == n, f"expected {n} rows; got {len(rows)}"


@then(
    'the database still contains {n:d} setpoint_recommendation rows for '
    '"{building_name}" from the prior run'
)
def step_assert_db_rec_still(context, n, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == n, f"expected {n} preserved rows; got {len(rows)}"


@then('no recommendation row references zone "{zone_name}" of "{building_name}"')
def step_assert_no_zone(context, zone_name, building_name):
    bid = _bid(context, building_name)
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    )
    rows = res.json()
    matching = [r for r in rows if r["zone_id"] == zone_id]
    assert not matching, f"unexpected rows referencing zone {zone_name}: {matching}"


@then(
    "the projected_savings_kwh sequence over the ranked rows is monotonically non-increasing"
)
def step_assert_monotonic(context):
    body = context.last_response.json()
    rows = sorted(body["recommendations"], key=lambda r: r["rank"])
    prev = None
    for r in rows:
        val = float(r["projected_savings_kwh"])
        if prev is not None:
            assert val <= prev, f"ranking not monotonic: {prev} -> {val}"
        prev = val


@then("every recommendation row has a projected_savings_kwh greater than or equal to 0")
def step_assert_savings_nonneg(context):
    body = context.last_response.json()
    for r in body["recommendations"]:
        assert float(r["projected_savings_kwh"]) >= 0, f"negative savings: {r}"


@then('every recommendation row has a comfort_impact in "{csv}"')
def step_assert_comfort_impact_enum(context, csv):
    allowed = {x.strip() for x in csv.split(",")}
    body = context.last_response.json()
    for r in body["recommendations"]:
        assert r["comfort_impact"] in allowed, (
            f"comfort_impact {r['comfort_impact']!r} not in {allowed}"
        )


@then("the ranked recommendations match the baseline exactly")
def step_assert_baseline_match(context):
    body = context.last_response.json()
    current = [
        (
            r["zone_id"],
            str(r["setpoint_delta_f"]),
            str(r["projected_savings_kwh"]),
            r["comfort_impact"],
            r["rank"],
        )
        for r in body["recommendations"]
    ]
    assert current == context.rec_baseline, (
        f"determinism violated: baseline={context.rec_baseline} current={current}"
    )


@then("the recommendation run completes in under {limit_ms:d} milliseconds")
def step_assert_perf(context, limit_ms):
    body = context.last_response.json()
    assert body.get("elapsed_ms", 0) < limit_ms, (
        f"server-reported elapsed_ms={body.get('elapsed_ms')} exceeds {limit_ms}"
    )
    assert context.last_elapsed_ms < limit_ms, (
        f"client-observed elapsed_ms={context.last_elapsed_ms:.1f} exceeds {limit_ms}"
    )


@then('the RecommendationsPage displays {n:d} recommendation rows for "{building_name}"')
def step_ui_rec_rows(context, n, building_name):
    context.page.goto(f"{context.frontend_url}/recommendations")
    context.page.wait_for_selector('[data-testid="recommendation-building-selector"]')
    context.page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="recommendation-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    context.page.select_option(
        '[data-testid="recommendation-building-selector"]', label=building_name
    )
    context.page.wait_for_selector('[data-testid="recommendation-table"]', timeout=5_000)
    rows = context.page.locator('[data-testid^="recommendation-row-"]')
    assert rows.count() == n, f"expected {n} UI rows; got {rows.count()}"


@then('the RecommendationsPage displays no recommendation rows for "{building_name}"')
def step_ui_no_rec_rows(context, building_name):
    rows = context.page.locator('[data-testid^="recommendation-row-"]')
    assert rows.count() == 0, f"expected 0 UI rows; got {rows.count()}"


@then('the RecommendationsPage shows an error banner listing "{label}"')
def step_ui_rec_error(context, label):
    context.page.wait_for_selector(
        '[data-testid="recommendation-run-error"]', timeout=5_000
    )
    text = context.page.locator(
        '[data-testid="recommendation-missing-inputs"]'
    ).inner_text()
    assert label in text, f"{label!r} not in error banner: {text!r}"


@then("the RecommendationsPage run button is re-enabled")
def step_ui_run_button_enabled(context):
    btn = context.page.locator('[data-testid="recommendation-run-button"]')
    assert not btn.is_disabled(), "recommendation-run-button is still disabled"
