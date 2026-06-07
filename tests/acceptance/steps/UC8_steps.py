"""UC8 ExplainRecommendation step definitions.

Reuses background steps from UC1/UC3/UC4/UC7 via behave's global step registry.
"""
import json
import time
from decimal import Decimal

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


def _latest_recs(context, building_name) -> list[dict]:
    bid = _bid(context, building_name)
    res = httpx.get(
        f"{context.backend_url}/api/buildings/{bid}/recommendations/latest",
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"latest recommendations failed: {res.status_code} {res.text}"
    )
    return res.json()


def _recommendation_for_zone(context, zone_name, building_name) -> dict:
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    rows = _latest_recs(context, building_name)
    matching = [r for r in rows if r["zone_id"] == zone_id]
    assert matching, (
        f"no recommendation for zone {zone_name!r} of {building_name!r}; "
        f"rows={rows}"
    )
    # If multiple, take the first (UC4 emits a single per zone).
    return matching[0]


def _post_explain(context, recommendation_id: int) -> httpx.Response:
    start = time.perf_counter()
    res = httpx.post(
        f"{context.backend_url}/api/recommendations/{recommendation_id}/explain",
        timeout=15.0,
    )
    context.last_response = res
    context.last_elapsed_ms = (time.perf_counter() - start) * 1000.0
    return res


def _get_explanation(context, recommendation_id: int) -> httpx.Response:
    res = httpx.get(
        f"{context.backend_url}/api/recommendations/{recommendation_id}/explanation",
        timeout=15.0,
    )
    context.last_response = res
    return res


def _count_explanations_for_recommendation(recommendation_id: int) -> int:
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM recommendation_explanations "
                    "WHERE recommendation_id = :r"
                ),
                {"r": recommendation_id},
            ).first()
            return int(row[0]) if row else 0
    finally:
        engine.dispose()


def _row_model_version_for_recommendation(recommendation_id: int) -> str | None:
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT model_version FROM recommendation_explanations "
                    "WHERE recommendation_id = :r"
                ),
                {"r": recommendation_id},
            ).first()
            return row[0] if row else None
    finally:
        engine.dispose()


# -- Background extensions ---------------------------------------------------


@given("the ExplanationAdapter test double is reset")
def step_explanation_double_reset(context):
    res = httpx.post(
        f"{context.backend_url}/api/_test/explanation/reset",
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"explanation reset failed: {res.status_code} {res.text}"
    )


@given("the ExplanationService is configured to force a DB error on the next request")
def step_explanation_force_db_error(context):
    res = httpx.post(
        f"{context.backend_url}/api/_test/explanation/force_db_error",
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"force db error failed: {res.status_code} {res.text}"
    )


@given('the latest recommendation factor fields for zone "{dst_zone}" of "{building_name}" are copied from zone "{src_zone}" of "{src_building}"')
def step_copy_recommendation_fields(context, dst_zone, building_name, src_zone, src_building):
    dst_zones = _zones(context, building_name)
    src_zones = _zones(context, src_building)
    res = httpx.post(
        f"{context.backend_url}/api/_test/recommendations/copy_fields_between_zones",
        json={
            "src_zone_id": src_zones[src_zone],
            "dst_zone_id": dst_zones[dst_zone],
        },
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"copy fields failed: {res.status_code} {res.text}"
    )


@given('all occupancy records for zone "{zone_name}" of "{building_name}" are deleted')
def step_clear_all_occupancy(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    res = httpx.post(
        f"{context.backend_url}/api/_test/clear_occupancy_for_zone",
        json={"zone_id": zone_id},
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"clear occupancy failed: {res.status_code} {res.text}"
    )


# -- Actions -----------------------------------------------------------------


@when('the FacilityManager requests an explanation for the latest recommendation of zone "{zone_name}" of "{building_name}"')
def step_when_explain_latest_for_zone(context, zone_name, building_name):
    _activate(context, building_name)
    rec = _recommendation_for_zone(context, zone_name, building_name)
    context.last_recommendation = rec
    _post_explain(context, int(rec["id"]))


@when("the FacilityManager requests an explanation for recommendation id {rid:d}")
def step_when_explain_by_id(context, rid):
    _post_explain(context, int(rid))


@when('the FacilityManager fetches the explanation for the latest recommendation of zone "{zone_name}" of "{building_name}"')
def step_when_get_explanation(context, zone_name, building_name):
    _activate(context, building_name)
    rec = _recommendation_for_zone(context, zone_name, building_name)
    context.last_recommendation = rec
    _get_explanation(context, int(rec["id"]))


@when('the explanation text is captured as the baseline for zone "{zone_name}" of "{building_name}"')
def step_when_capture_baseline(context, zone_name, building_name):
    body = context.last_response.json()
    context.explain_baseline_text = body["text"]
    context.explain_baseline_zone = zone_name
    context.explain_baseline_building = building_name


@when('the user requests an explanation for zone "{zone_name}" of "{building_name}" via the ExplainPage')
def step_when_ui_explain(context, zone_name, building_name):
    _activate(context, building_name)
    rec = _recommendation_for_zone(context, zone_name, building_name)
    context.last_recommendation = rec
    page = context.page
    page.goto(
        f"{context.frontend_url}/explain?recommendation_id={int(rec['id'])}"
    )
    page.wait_for_selector('[data-testid="explain-recommendation-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="explain-recommendation-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.click('[data-testid="explain-run-button"]')
    page.wait_for_selector(
        '[data-testid="explain-success-banner"], [data-testid="explain-error-banner"]',
        timeout=15_000,
    )


@when('the user requests an explanation for zone "{zone_name}" of "{building_name}" via the ExplainPage again')
def step_when_ui_explain_again(context, zone_name, building_name):
    page = context.page
    page.click('[data-testid="explain-run-button"]')
    page.wait_for_selector(
        '[data-testid="explain-cached-pill"]',
        timeout=15_000,
    )


# -- Assertions --------------------------------------------------------------


@then("the explanation response status is {code:d}")
def step_then_status(context, code):
    res = context.last_response
    assert res.status_code == code, (
        f"expected {code}; got {res.status_code}: {res.text}"
    )


@then('the explanation text contains case-insensitive substring "{needle}"')
def step_then_text_substring(context, needle):
    body = context.last_response.json()
    assert needle.lower() in body["text"].lower(), (
        f"text {body['text']!r} does not contain case-insensitive {needle!r}"
    )


@then("the explanation text contains the projected_savings_kwh value")
def step_then_text_has_savings(context):
    rec = context.last_recommendation
    body = context.last_response.json()
    # Format the savings to three decimals (matches the double's template).
    savings = f"{Decimal(str(rec['projected_savings_kwh'])):.3f}"
    assert savings in body["text"], (
        f"savings {savings!r} not found in text {body['text']!r}"
    )


@then("the explanation text contains the comfort_impact value")
def step_then_text_has_comfort_impact(context):
    rec = context.last_recommendation
    body = context.last_response.json()
    impact = str(rec["comfort_impact"])
    assert impact in body["text"], (
        f"comfort_impact {impact!r} not found in text {body['text']!r}"
    )


@then("the explanation text contains the latest occupancy_count value")
def step_then_text_has_occupancy_count(context):
    body = context.last_response.json()
    rec = context.last_recommendation
    # The default fixture seeds occupancy_count=2 per UC3 background step.
    # Look it up directly from the DB so the step adapts to any seed change.
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT occupancy_count FROM occupancy_records "
                    "WHERE zone_id = :z "
                    "ORDER BY timestamp DESC LIMIT 1"
                ),
                {"z": int(rec["zone_id"])},
            ).first()
    finally:
        engine.dispose()
    assert row is not None, "no occupancy row found for zone"
    count = int(row[0])
    assert f"{count}" in body["text"], (
        f"occupancy count {count} not found in text {body['text']!r}"
    )


@then('the explanation factors object has a non-empty "{key}" entry')
def step_then_factors_key(context, key):
    body = context.last_response.json()
    factors = body.get("factors", {})
    assert key in factors, f"factors missing key {key!r}: {factors}"
    value = factors[key]
    assert isinstance(value, str) and value.strip(), (
        f"factors[{key!r}] is empty: {value!r}"
    )


@then('the explanation response has cached "{flag}"')
def step_then_cached(context, flag):
    body = context.last_response.json()
    expected = flag.lower() == "true"
    actual = bool(body.get("cached"))
    assert actual == expected, (
        f"cached={actual} expected {expected}; body={body}"
    )


@then("the explanation adapter has been invoked {n:d} time")
def step_then_calls_count_singular(context, n):
    _assert_calls_count(context, n)


@then("the explanation adapter has been invoked {n:d} times")
def step_then_calls_count(context, n):
    _assert_calls_count(context, n)


def _assert_calls_count(context, expected: int) -> None:
    res = httpx.get(
        f"{context.backend_url}/api/_test/explanation/calls",
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"calls endpoint failed: {res.status_code} {res.text}"
    )
    actual = int(res.json()["calls"])
    assert actual == expected, (
        f"adapter calls_count={actual} expected {expected}"
    )


@then('the database contains {n:d} recommendation_explanations row for the latest recommendation of zone "{zone_name}" of "{building_name}"')
def step_then_db_count_for_zone(context, n, zone_name, building_name):
    # Resolve the recommendation row; if no recommendation exists for the
    # zone (e.g. zone is in a different building), count is implicitly 0.
    zones = _zones(context, building_name)
    if zone_name not in zones:
        assert n == 0, (
            f"zone {zone_name!r} not found in {building_name!r}; expected count {n}"
        )
        return
    zone_id = zones[zone_name]
    rows = _latest_recs(context, building_name)
    matching = [r for r in rows if r["zone_id"] == zone_id]
    if not matching:
        assert n == 0, (
            f"no recommendation found for zone {zone_name!r}; expected count {n}"
        )
        return
    rid = int(matching[0]["id"])
    actual = _count_explanations_for_recommendation(rid)
    assert actual == n, (
        f"expected {n} recommendation_explanations rows for rec {rid}; got {actual}"
    )


@then("the explanation response missingInputs equals {payload}")
def step_then_missing_inputs_equals(context, payload):
    body = context.last_response.json()
    actual = body.get("detail", {}).get("missingInputs", [])
    expected = json.loads(payload)
    assert actual == expected, (
        f"missingInputs={actual} expected {expected}; full body={body}"
    )


@then("the explanation response elapsed_ms is under {limit_ms:d}")
def step_then_elapsed(context, limit_ms):
    body = context.last_response.json()
    elapsed = float(body.get("elapsed_ms", 0))
    assert elapsed < limit_ms, (
        f"elapsed_ms={elapsed} exceeds {limit_ms}"
    )


@then('the explanation response model_version equals "{value}"')
def step_then_model_version_api(context, value):
    body = context.last_response.json()
    assert body.get("model_version") == value, (
        f"model_version={body.get('model_version')!r} expected {value!r}"
    )


@then('the persisted recommendation_explanations row model_version equals "{value}" for the latest recommendation of zone "{zone_name}" of "{building_name}"')
def step_then_model_version_row(context, value, zone_name, building_name):
    rec = _recommendation_for_zone(context, zone_name, building_name)
    rid = int(rec["id"])
    actual = _row_model_version_for_recommendation(rid)
    assert actual == value, (
        f"row.model_version={actual!r} expected {value!r}"
    )


@then('the explanation text for zone "{zone_a}" of "{bldg_a}" matches the baseline for zone "{zone_b}" of "{bldg_b}" modulo identifiers')
def step_then_text_matches_baseline(context, zone_a, bldg_a, zone_b, bldg_b):
    body = context.last_response.json()
    assert hasattr(context, "explain_baseline_text"), (
        "baseline text not captured"
    )
    # The double's text does not embed any recommendation_id, so plain equality
    # is the "modulo identifiers" oracle for UC8-S04.
    assert body["text"] == context.explain_baseline_text, (
        f"text differs: current={body['text']!r} baseline={context.explain_baseline_text!r}"
    )


# -- UI assertions -----------------------------------------------------------


@then("the ExplainPage shows the success banner")
def step_then_ui_success(context):
    context.page.wait_for_selector(
        '[data-testid="explain-success-banner"]', timeout=5_000
    )


@then("the ExplainPage shows the explanation text")
def step_then_ui_text(context):
    el = context.page.locator('[data-testid="explain-text"]')
    txt = el.inner_text().strip()
    assert txt, "explain-text is empty"


@then("the ExplainPage shows the three factor sections")
def step_then_ui_factors(context):
    for key in ("energy", "comfort", "occupancy"):
        el = context.page.locator(f'[data-testid="explain-factor-{key}"]')
        txt = el.inner_text().strip()
        assert txt, f"explain-factor-{key} is empty"


@then("the ExplainPage shows the model-version pill")
def step_then_ui_model_pill(context):
    el = context.page.locator('[data-testid="explain-model-version"]')
    txt = el.inner_text().strip()
    assert txt == "explanation-double-v1", (
        f"model-version pill reads {txt!r}"
    )


@then("the ExplainPage shows the cached pill")
def step_then_ui_cached_pill(context):
    context.page.wait_for_selector(
        '[data-testid="explain-cached-pill"]', timeout=5_000
    )
