"""UC6 AdaptPlanToOccupancyChange step definitions.

Reuses background steps from UC1/UC3/UC4/UC5_steps.py via behave's global
step registry.
"""
import json
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
            return r["id"]
    raise AssertionError(
        f"rank {rank} not found in latest recs for {building_name}: {rows}"
    )


def _adapt(context, building_name, occupancy_changes):
    bid = _bid(context, building_name)
    _activate(context, building_name)
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/plan/adapt",
        json={"occupancy_changes": occupancy_changes},
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = (time.perf_counter() - start) * 1000.0
    context.last_adapt_payload = occupancy_changes
    return res


def _list_adaptations(context, building_name):
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/plan/adaptations",
        timeout=5.0,
    )
    assert res.status_code == 200, f"list adaptations failed: {res.status_code}"
    return res.json()


def _rec_count(context, building_name):
    # Use latest_for_building as a proxy for "rows in the latest run".
    # We compare run_timestamp before/after to detect a new run.
    rows = _latest_recs(context, building_name)
    return rows[0]["run_timestamp"] if rows else None


# -- Background extensions ---------------------------------------------------


@given('the FacilityManager has applied the rank {rank:d} recommendation for "{building_name}"')
def step_given_fm_applied(context, rank, building_name):
    bid = _bid(context, building_name)
    rid = _rec_id_for_rank(context, building_name, rank)
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/plans/apply",
        json={"recommendation_ids": [rid]},
        timeout=15.0,
    )
    assert res.status_code == 200, (
        f"apply for active-plan setup failed: {res.status_code} {res.text}"
    )
    # Snapshot the latest run's timestamp so subsequent assertions can detect
    # whether a NEW run was created.
    try:
        pre_map = context._pre_adapt_run_ts_by_building
    except (KeyError, AttributeError):
        pre_map = {}
        context._pre_adapt_run_ts_by_building = pre_map
    pre_map[building_name] = _rec_count(context, building_name)


@given('the FacilityManager applies the rank {ranks} recommendations for "{building_name}"')
def step_given_fm_applies_ranks(context, ranks, building_name):
    bid = _bid(context, building_name)
    rank_list = [int(s.strip()) for s in ranks.split(",")]
    ids = [_rec_id_for_rank(context, building_name, r) for r in rank_list]
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{bid}/plans/apply",
        json={"recommendation_ids": ids},
        timeout=15.0,
    )
    assert res.status_code == 200, (
        f"multi-rank apply setup failed: {res.status_code} {res.text}"
    )


@given('the latest occupancy snapshot for zone "{zone_name}" of "{building_name}" is set to {n:d}')
def step_set_zone_baseline(context, zone_name, building_name, n):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    res = httpx.post(
        f"{context.backend_url}/api/_test/occupancy/set_for_zone",
        json={"zone_id": zone_id, "occupancy_count": n},
        timeout=5.0,
    )
    assert res.status_code == 200, f"set_for_zone failed: {res.status_code}"


# -- Actions -----------------------------------------------------------------


@when('the OccupancyDataService reports occupancy changes for "{building_name}"')
def step_when_report_occupancy_changes(context, building_name):
    zones = _zones(context, building_name)
    changes = []
    for row in context.table:
        zone_name = row["zone_name"]
        new_count = int(row["new_occupancy_count"])
        changes.append({"zone_id": zones[zone_name], "new_occupancy_count": new_count})
    _adapt(context, building_name, changes)


@when('the OccupancyDataService reports the same occupancy changes for "{building_name}" again')
def step_when_report_same_again(context, building_name):
    res = _adapt(context, building_name, context.last_adapt_payload)
    context.second_response = res


@when('the OccupancyDataService reports a {pct:d} percent jump for zone "{zone_name}" of "{building_name}"')
def step_when_pct_jump(context, pct, zone_name, building_name):
    # Force baseline=100 for crisp arithmetic. The seeded snapshot sits at the
    # epoch (1970) so it falls BEFORE any active-plan run_timestamp.
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    httpx.post(
        f"{context.backend_url}/api/_test/occupancy/set_for_zone",
        json={"zone_id": zone_id, "occupancy_count": 100},
        timeout=5.0,
    )
    new_count = 100 + pct  # 29% -> 129, 30% -> 130
    _adapt(
        context,
        building_name,
        [{"zone_id": zone_id, "new_occupancy_count": new_count}],
    )


@when('the OccupancyDataService reports an occupancy change against an unknown building id')
def step_when_unknown_building(context):
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/buildings/9999999/plan/adapt",
        json={"occupancy_changes": [{"zone_id": 1, "new_occupancy_count": 10}]},
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = (time.perf_counter() - start) * 1000.0


@when('the OccupancyDataService reports occupancy changes for "{building_name}" referencing an unknown zone')
def step_when_unknown_zone(context, building_name):
    _adapt(
        context,
        building_name,
        [{"zone_id": 9_999_999, "new_occupancy_count": 50}],
    )


@when('the OccupancyDataService reports an empty occupancy_changes payload for "{building_name}"')
def step_when_empty_payload(context, building_name):
    _adapt(context, building_name, [])


@when('the user submits an occupancy change for zone "{zone_name}" of "{building_name}" with count {n:d} via the AdaptPlanPage')
def step_when_ui_submit(context, zone_name, building_name, n):
    _activate(context, building_name)
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    page = context.page
    page.goto(f"{context.frontend_url}/adapt-plan")
    page.wait_for_selector('[data-testid="adapt-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="adapt-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="adapt-building-selector"]', label=building_name
    )
    page.wait_for_selector(f'[data-testid="adapt-zone-row-{zone_id}"]', timeout=5_000)
    page.fill(f'[data-testid="adapt-occupancy-input-{zone_id}"]', str(n))
    page.click('[data-testid="adapt-run-button"]')
    page.wait_for_selector(
        '[data-testid="adapt-success-banner"], [data-testid="adapt-error-banner"]',
        timeout=15_000,
    )


# -- Assertions --------------------------------------------------------------


@then('the adapt response has decision "{decision}"')
def step_then_decision(context, decision):
    res = context.last_response
    assert res.status_code == 200, f"expected 200; got {res.status_code}: {res.text}"
    body = res.json()
    assert body["decision"] == decision, (
        f"decision={body['decision']} expected {decision}"
    )


@then('the second adapt response has decision "{decision}"')
def step_then_second_decision(context, decision):
    res = context.second_response
    assert res.status_code == 200, f"expected 200; got {res.status_code}: {res.text}"
    body = res.json()
    assert body["decision"] == decision, (
        f"second decision={body['decision']} expected {decision}"
    )


@then('the adapt response changed_zone_ids list zones {zone_list_json} for "{building_name}"')
def step_then_changed_zones(context, zone_list_json, building_name):
    expected_names = json.loads(zone_list_json)
    zones = _zones(context, building_name)
    expected_ids = {zones[n] for n in expected_names}
    body = context.last_response.json()
    actual_ids = set(body["changed_zone_ids"])
    assert actual_ids == expected_ids, (
        f"changed_zone_ids={actual_ids} expected={expected_ids}"
    )


@then("the adapt response includes a non-null new_run_timestamp")
def step_then_new_run_ts_not_null(context):
    body = context.last_response.json()
    assert body.get("new_run_timestamp") is not None, body


@then("the adapt response new_run_timestamp is null")
def step_then_new_run_ts_null(context):
    body = context.last_response.json()
    assert body.get("new_run_timestamp") is None, body


@then('the database contains {n:d} plan_adaptation_events rows for "{building_name}"')
def step_then_db_event_count(context, n, building_name):
    rows = _list_adaptations(context, building_name)
    assert len(rows) == n, f"expected {n} adapt events; got {len(rows)}"


@then('a new setpoint_recommendations run was created for "{building_name}"')
def step_then_new_run_created(context, building_name):
    try:
        pre_ts = context._pre_adapt_run_ts_by_building.get(building_name)
    except (KeyError, AttributeError):
        pre_ts = None
    current_ts = _rec_count(context, building_name)
    assert current_ts is not None, "no recommendations after adapt"
    assert current_ts != pre_ts, (
        f"expected a new rec run; before={pre_ts} after={current_ts}"
    )


@then('no new setpoint_recommendations run was created for "{building_name}"')
def step_then_no_new_run(context, building_name):
    try:
        pre_ts = context._pre_adapt_run_ts_by_building.get(building_name)
    except (KeyError, AttributeError):
        pre_ts = None
    current_ts = _rec_count(context, building_name)
    assert current_ts == pre_ts, (
        f"unexpected new rec run; before={pre_ts} after={current_ts}"
    )


@then('the adapt is rejected with a missing-inputs error listing "{label}"')
def step_then_adapt_missing(context, label):
    res = context.last_response
    assert res.status_code == 400, f"expected 400; got {res.status_code}: {res.text}"
    body = res.json()
    missing = body.get("detail", {}).get("missingInputs", [])
    assert label in missing, f"{label!r} not in missingInputs={missing}"


@then("the adapt call completes in under {limit_ms:d} milliseconds")
def step_then_adapt_perf(context, limit_ms):
    body = context.last_response.json()
    assert body.get("elapsed_ms", 0) < limit_ms, (
        f"server-reported elapsed_ms={body.get('elapsed_ms')} exceeds {limit_ms}"
    )
    assert context.last_elapsed_ms < limit_ms, (
        f"client-observed elapsed_ms={context.last_elapsed_ms:.1f} exceeds {limit_ms}"
    )


@then("the AdaptPlanPage shows the success banner")
def step_then_ui_success(context):
    context.page.wait_for_selector(
        '[data-testid="adapt-success-banner"]', timeout=5_000
    )


@then('the AdaptPlanPage decision pill reads "{decision}"')
def step_then_ui_decision(context, decision):
    pill = context.page.locator('[data-testid="adapt-decision-pill"]')
    text = pill.inner_text().strip()
    assert text == decision, f"pill reads {text!r}; expected {decision!r}"


@then("the AdaptPlanPage reason text is non-empty")
def step_then_ui_reason(context):
    text = context.page.locator('[data-testid="adapt-reason-text"]').inner_text().strip()
    assert text, "reason text empty"


@then('the AdaptPlanPage lists zone "{zone_name}" of "{building_name}" as a changed zone')
def step_then_ui_changed_zone(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zid = zones[zone_name]
    context.page.wait_for_selector(
        f'[data-testid="adapt-changed-zone-{zid}"]', timeout=5_000
    )


@then("the AdaptPlanPage revised-recs table displays {n:d} rows")
def step_then_ui_rev_recs(context, n):
    rows = context.page.locator('[data-testid^="adapt-revised-rec-row-"]')
    assert rows.count() == n, f"expected {n} revised-rec rows; got {rows.count()}"
