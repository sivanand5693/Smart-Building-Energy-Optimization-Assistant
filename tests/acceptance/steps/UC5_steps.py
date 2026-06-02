"""UC5 ApplyApprovedEnergyPlan step definitions.

Reuses building / forecast / recommendation steps from UC1/UC3/UC4_steps.py
via behave's global step registry.
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


def _latest_recs(context, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    )
    assert res.status_code == 200, f"latest recs failed: {res.status_code}"
    return res.json()


def _rec_id_for_rank(context, building_name, rank):
    rows = _latest_recs(context, building_name)
    for r in rows:
        if r["rank"] == rank:
            assert r.get("id") is not None, (
                f"recommendation row missing 'id' field: {r}"
            )
            return r["id"]
    raise AssertionError(
        f"rank {rank} not found in latest recs for {building_name}: {rows}"
    )


def _apply(context, building_name, ids):
    bid = _bid(context, building_name)
    _activate(context, building_name)
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/plans/apply",
        json={"recommendation_ids": ids},
        timeout=30.0,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    context.last_response = res
    context.last_elapsed_ms = elapsed_ms
    return res


# -- Background extensions ---------------------------------------------------


@given("the DeviceControlAdapter test double is reset")
def step_reset_device_control(context):
    httpx.post(
        f"{context.backend_url}/api/_test/device_control/reset", timeout=5.0
    )


@given('the HVAC devices for zone "{zone_name}" of "{building_name}" are deleted')
def step_clear_hvac(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/devices/clear_for_zone",
        json={"zone_id": zone_id},
        timeout=5.0,
    )


@given(
    'the DeviceControlAdapter is configured to fail the rank {rank:d} '
    'recommendation of "{building_name}" with error_code "{error_code}"'
)
def step_directive_fail_rank(context, rank, building_name, error_code):
    rid = _rec_id_for_rank(context, building_name, rank)
    httpx.post(
        f"{context.backend_url}/api/_test/device_control/directive",
        json={
            "recommendation_id": rid,
            "outcome": "failed",
            "error_code": error_code,
            "adapter_message": f"forced {error_code}",
            "latency_ms": 7,
        },
        timeout=5.0,
    )


@given('the DeviceControlAdapter is configured to force a DB error on the next apply for "{building_name}"')
def step_force_db_error(context, building_name):
    httpx.post(
        f"{context.backend_url}/api/_test/device_control/force_db_error",
        timeout=5.0,
    )


@given('the previous recommendation run for "{building_name}" is captured as the stale run')
def step_capture_stale_run(context, building_name):
    rows = _latest_recs(context, building_name)
    context.stale_run = rows


@given('a new successful recommendation run exists for "{building_name}" with {n:d} recommendation rows')
def step_new_rec_run(context, building_name, n):
    bid = _bid(context, building_name)
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/run",
        timeout=15.0,
    )
    assert res.status_code == 200, (
        f"new rec run failed: {res.status_code} {res.text}"
    )
    body = res.json()
    assert len(body["recommendations"]) == n, (
        f"new run produced {len(body['recommendations'])} rows; expected {n}"
    )


# -- Actions -----------------------------------------------------------------


@when('the FacilityManager applies the rank {rank:d} recommendation for "{building_name}"')
def step_apply_rank(context, rank, building_name):
    rid = _rec_id_for_rank(context, building_name, rank)
    _apply(context, building_name, [rid])


@when('the FacilityManager applies the rank {rank:d} recommendation for "{building_name}" again')
def step_apply_rank_again(context, rank, building_name):
    rid = _rec_id_for_rank(context, building_name, rank)
    res = _apply(context, building_name, [rid])
    context.second_response = res


@when('the FacilityManager applies the rank {ranks} recommendations for "{building_name}"')
def step_apply_ranks(context, ranks, building_name):
    rank_list = [int(s.strip()) for s in ranks.split(",")]
    ids = [_rec_id_for_rank(context, building_name, r) for r in rank_list]
    _apply(context, building_name, ids)


@when('the FacilityManager applies all recommendations of the latest run for "{building_name}"')
def step_apply_all(context, building_name):
    rows = _latest_recs(context, building_name)
    ids = [r["id"] for r in rows]
    _apply(context, building_name, ids)


@when('the FacilityManager applies the rank {rank:d} recommendation for an unknown building id')
def step_apply_unknown_building(context, rank):
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/9999999/plans/apply",
        json={"recommendation_ids": [1]},
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = (time.perf_counter() - start) * 1000.0


@when('the FacilityManager applies an unknown recommendation id for "{building_name}"')
def step_apply_unknown_rec(context, building_name):
    _apply(context, building_name, [9_999_999])


@when('the FacilityManager applies the rank {rank:d} recommendation of "{other}" against building "{target}"')
def step_apply_cross_building(context, rank, other, target):
    rid = _rec_id_for_rank(context, other, rank)
    _apply(context, target, [rid])


@when('the FacilityManager applies the captured stale rank {rank:d} recommendation for "{building_name}"')
def step_apply_stale(context, rank, building_name):
    stale_rows = context.stale_run
    rid = next((r["id"] for r in stale_rows if r["rank"] == rank), None)
    assert rid is not None, f"no captured stale row with rank {rank}"
    _apply(context, building_name, [rid])


@when('the user applies all recommendations of the latest run for "{building_name}" via the ApplyPlanPage')
def step_ui_apply_all(context, building_name):
    _activate(context, building_name)
    page = context.page
    page.goto(f"{context.frontend_url}/apply-plan")
    page.wait_for_selector('[data-testid="apply-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="apply-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="apply-building-selector"]', label=building_name
    )
    page.wait_for_selector('[data-testid="latest-run-table"]', timeout=5_000)
    page.click('[data-testid="apply-run-button"]')
    page.wait_for_selector(
        '[data-testid="apply-result-table"], [data-testid="apply-error-banner"]',
        timeout=15_000,
    )


# -- Assertions --------------------------------------------------------------


@then("the apply result contains {n:d} result rows")
def step_assert_result_count(context, n):
    res = context.last_response
    assert res.status_code == 200, f"expected 200; got {res.status_code}: {res.text}"
    body = res.json()
    assert len(body["results"]) == n, (
        f"expected {n} results; got {len(body['results'])}"
    )


@then("the second apply result contains {n:d} result rows")
def step_assert_second_result_count(context, n):
    res = context.second_response
    assert res.status_code == 200, f"expected 200; got {res.status_code}: {res.text}"
    body = res.json()
    assert len(body["results"]) == n, (
        f"expected {n} results; got {len(body['results'])}"
    )


@then('every apply result row has status "{status}"')
def step_assert_all_status(context, status):
    body = context.last_response.json()
    for r in body["results"]:
        assert r["status"] == status, f"row {r} has status != {status}"


@then("the apply result rows are ordered by rank ascending")
def step_assert_result_order(context):
    body = context.last_response.json()
    bid = body["building_id"]
    recs = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    ).json()
    rank_of = {r["id"]: r["rank"] for r in recs}
    ranks = [rank_of[r["recommendation_id"]] for r in body["results"]]
    assert ranks == sorted(ranks), f"results not in rank ASC order: {ranks}"


@then('the DeviceControlAdapter was invoked {n:d} times for "{building_name}" in rank ascending order')
def step_assert_adapter_calls_ordered(context, n, building_name):
    res = httpx.get(
        f"{context.backend_url}/api/_test/device_control/calls", timeout=5.0
    )
    calls = res.json()["calls"]
    recs = _latest_recs(context, building_name)
    rec_ids_for_building = {r["id"] for r in recs}
    filtered = [c for c in calls if c["recommendation_id"] in rec_ids_for_building]
    assert len(filtered) == n, (
        f"expected {n} adapter calls for {building_name}; got {len(filtered)}"
    )
    rank_of = {r["id"]: r["rank"] for r in recs}
    seen_ranks = [rank_of[c["recommendation_id"]] for c in filtered]
    assert seen_ranks == sorted(seen_ranks), (
        f"adapter calls not in rank ASC order: {seen_ranks}"
    )


@then('the DeviceControlAdapter was invoked {n:d} times for "{building_name}"')
def step_assert_adapter_call_count(context, n, building_name):
    res = httpx.get(
        f"{context.backend_url}/api/_test/device_control/calls", timeout=5.0
    )
    calls = res.json()["calls"]
    recs = _latest_recs(context, building_name)
    rec_ids_for_building = {r["id"] for r in recs}
    filtered = [c for c in calls if c["recommendation_id"] in rec_ids_for_building]
    assert len(filtered) == n, (
        f"expected {n} adapter calls for {building_name}; got {len(filtered)}"
    )


@then('the database contains {n:d} applied_setpoint_change rows for "{building_name}"')
def step_assert_db_apply_count(context, n, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/plans/latest", timeout=5.0
    )
    assert res.status_code == 200, f"latest plan failed: {res.status_code}"
    rows = res.json()
    assert len(rows) == n, f"expected {n} applied rows; got {len(rows)}"


@then(
    "each apply result row exposes recommendation_id, zone_id, setpoint_delta_f, "
    "status, error_code, adapter_message, and latency_ms"
)
def step_assert_result_fields(context):
    body = context.last_response.json()
    required = {
        "recommendation_id",
        "zone_id",
        "setpoint_delta_f",
        "status",
        "error_code",
        "adapter_message",
        "latency_ms",
    }
    for r in body["results"]:
        missing = required - r.keys()
        assert not missing, f"row missing fields {missing}: {r}"
        for f in required - {"error_code"}:
            assert r[f] is not None, f"field {f} is null in row {r}"


@then('the apply is rejected with a missing-inputs error listing "{label}"')
def step_apply_missing_inputs(context, label):
    res = context.last_response
    assert res.status_code == 400, (
        f"expected 400; got {res.status_code}: {res.text}"
    )
    body = res.json()
    missing = body.get("detail", {}).get("missingInputs", [])
    assert label in missing, f"{label!r} not in missingInputs={missing}"


@then('the second apply result row has status "{status}" with error_code "{code}"')
def step_assert_second_row_failed(context, status, code):
    body = context.second_response.json()
    r = body["results"][0]
    assert r["status"] == status, f"row status {r['status']} != {status}"
    assert r["error_code"] == code, f"error_code {r['error_code']} != {code}"


@then('the apply result row for zone "{zone_name}" of "{building_name}" has status "{status}" with error_code "{code}"')
def step_assert_result_row_for_zone(context, zone_name, building_name, status, code):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    body = context.last_response.json()
    matching = [r for r in body["results"] if r["zone_id"] == zone_id]
    assert matching, f"no result row for zone {zone_name} ({zone_id})"
    for r in matching:
        assert r["status"] == status, f"row for zone {zone_name}: status {r['status']} != {status}"
        assert r["error_code"] == code, f"row for zone {zone_name}: error_code {r['error_code']} != {code}"


@then('the apply result rows for zone "{zone_name}" of "{building_name}" all have status "{status}"')
def step_assert_zone_rows_status(context, zone_name, building_name, status):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    body = context.last_response.json()
    matching = [r for r in body["results"] if r["zone_id"] == zone_id]
    assert matching, f"no result row for zone {zone_name} ({zone_id})"
    for r in matching:
        assert r["status"] == status, f"row {r} status != {status}"


@then('the apply result row at rank {rank:d} has status "{status}" with error_code "{code}"')
def step_assert_row_at_rank_status_code(context, rank, status, code):
    body = context.last_response.json()
    bid = body["building_id"]
    recs = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    ).json()
    rank_of = {r["id"]: r["rank"] for r in recs}
    matching = [r for r in body["results"] if rank_of.get(r["recommendation_id"]) == rank]
    assert matching, f"no result row at rank {rank}"
    for r in matching:
        assert r["status"] == status, f"rank {rank} status {r['status']} != {status}"
        assert r["error_code"] == code, f"rank {rank} error_code {r['error_code']} != {code}"


@then('the apply result row at rank {rank:d} has status "{status}"')
def step_assert_row_at_rank_status(context, rank, status):
    body = context.last_response.json()
    bid = body["building_id"]
    recs = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    ).json()
    rank_of = {r["id"]: r["rank"] for r in recs}
    matching = [r for r in body["results"] if rank_of.get(r["recommendation_id"]) == rank]
    assert matching, f"no result row at rank {rank}"
    for r in matching:
        assert r["status"] == status, f"rank {rank} status {r['status']} != {status}"


@then("the apply call fails with HTTP 500")
def step_apply_fails_500(context):
    res = context.last_response
    assert res.status_code == 500, f"expected 500; got {res.status_code}: {res.text}"


@then("the apply call completes in under {limit_ms:d} milliseconds")
def step_apply_perf(context, limit_ms):
    body = context.last_response.json()
    assert body.get("elapsed_ms", 0) < limit_ms, (
        f"server-reported elapsed_ms={body.get('elapsed_ms')} exceeds {limit_ms}"
    )
    assert context.last_elapsed_ms < limit_ms, (
        f"client-observed elapsed_ms={context.last_elapsed_ms:.1f} exceeds {limit_ms}"
    )


@then('the ApplyPlanPage displays {n:d} apply-result rows for "{building_name}"')
def step_ui_assert_rows(context, n, building_name):
    rows = context.page.locator('[data-testid^="apply-result-row-"]')
    assert rows.count() == n, f"expected {n} apply-result rows; got {rows.count()}"


@then("the ApplyPlanPage shows the success banner")
def step_ui_success_banner(context):
    context.page.wait_for_selector(
        '[data-testid="apply-success-banner"]', timeout=5_000
    )


@then('every ApplyPlanPage apply-status pill reads "{status}"')
def step_ui_status_pills(context, status):
    pills = context.page.locator('[data-testid^="apply-status-"]')
    count = pills.count()
    assert count > 0, "no apply-status pills found"
    for i in range(count):
        text = pills.nth(i).inner_text().strip()
        assert text == status, f"pill {i} reads {text!r}, expected {status!r}"
