"""UC9 GenerateDailySavingsReport step definitions.

Reuses background steps from UC1/UC3 (`the system is initialized`, `a building
exists with zones`) via behave's global step registry.
"""
import json
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


def _post_run(
    context, building_id, payload: dict
) -> httpx.Response:
    res = httpx.post(
        f"{context.backend_url}/api/buildings/{building_id}/savings-reports/run",
        json=payload,
        timeout=15.0,
    )
    context.last_response = res
    return res


def _count_headers(building_id: int, report_date: str) -> int:
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM daily_savings_reports "
                    "WHERE building_id = :b AND report_date = :d"
                ),
                {"b": building_id, "d": report_date},
            ).first()
            return int(row[0]) if row else 0
    finally:
        engine.dispose()


def _count_lines(building_id: int, report_date: str) -> int:
    engine = create_engine(settings.test_database_url, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(l.*) FROM daily_savings_report_lines l "
                    "JOIN daily_savings_reports r ON r.id = l.report_id "
                    "WHERE r.building_id = :b AND r.report_date = :d"
                ),
                {"b": building_id, "d": report_date},
            ).first()
            return int(row[0]) if row else 0
    finally:
        engine.dispose()


def _line_for_zone(context, zone_name, building_name) -> dict:
    body = context.last_response.json()
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    matching = [ln for ln in body["lines"] if ln["zone_id"] == zone_id]
    assert matching, (
        f"no line for zone {zone_name!r} of {building_name!r} in body={body}"
    )
    return matching[0]


# -- Background steps --------------------------------------------------------


@given('energy usage rows are ingested for "{building_name}" on "{date_str}"')
def step_ingest_energy_usage(context, building_name, date_str):
    bid = _bid(context, building_name)
    zones = _zones(context, building_name)
    rows = []
    for row in context.table:
        zone_name = row["zone_name"]
        zone_id = zones[zone_name]
        baseline_cell = (row["baseline_kwh"] or "").strip()
        actual_cell = (row["actual_kwh"] or "").strip()
        if baseline_cell:
            rows.append(
                {
                    "building_id": bid,
                    "zone_id": zone_id,
                    "usage_date": date_str,
                    "kind": "baseline",
                    "kwh": float(baseline_cell),
                }
            )
        if actual_cell:
            rows.append(
                {
                    "building_id": bid,
                    "zone_id": zone_id,
                    "usage_date": date_str,
                    "kind": "actual",
                    "kwh": float(actual_cell),
                }
            )
    if not rows:
        return
    res = httpx.post(
        f"{context.backend_url}/api/_test/energy_usage/ingest",
        json={"rows": rows},
        timeout=10.0,
    )
    assert res.status_code == 200, (
        f"energy usage ingest failed: {res.status_code} {res.text}"
    )


@given("the ReportingService is configured to force a DB error on the next request")
def step_force_db_error(context):
    res = httpx.post(
        f"{context.backend_url}/api/_test/savings/force_db_error",
        timeout=5.0,
    )
    assert res.status_code == 200, (
        f"force db error failed: {res.status_code} {res.text}"
    )


# -- Actions -----------------------------------------------------------------


@when(
    'the FacilityManager generates a savings report for "{building_name}" '
    'on "{date_str}"'
)
def step_generate_for_building_on_date(context, building_name, date_str):
    bid = _bid(context, building_name)
    _post_run(context, bid, {"report_date": date_str})


@when(
    'the FacilityManager generates a savings report for unknown building id '
    '{bid:d} on "{date_str}"'
)
def step_generate_unknown_building(context, bid, date_str):
    _post_run(context, bid, {"report_date": date_str})


@when(
    'the FacilityManager generates a savings report for "{building_name}" '
    'with report_date "{date_str}"'
)
def step_generate_with_literal_date(context, building_name, date_str):
    bid = _bid(context, building_name)
    _post_run(context, bid, {"report_date": date_str})


@when(
    'the user generates a savings report for "{building_name}" on '
    '"{date_str}" via the SavingsReportPage'
)
def step_ui_generate(context, building_name, date_str):
    page = context.page
    page.goto(f"{context.frontend_url}/savings-report")
    page.wait_for_selector('[data-testid="savings-building-selector"]')
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="savings-building-selector"] option').length > 0""",
        timeout=5_000,
    )
    page.select_option(
        '[data-testid="savings-building-selector"]', label=building_name
    )
    page.fill('[data-testid="savings-date-input"]', date_str)
    page.click('[data-testid="savings-run-button"]')
    page.wait_for_selector(
        '[data-testid="savings-success-banner"], [data-testid="savings-error-banner"]',
        timeout=15_000,
    )


@when(
    'the user generates a savings report for "{building_name}" on '
    '"{date_str}" via the SavingsReportPage again'
)
def step_ui_generate_again(context, building_name, date_str):
    page = context.page
    page.click('[data-testid="savings-run-button"]')
    page.wait_for_selector(
        '[data-testid="savings-cached-pill"]',
        timeout=15_000,
    )


# -- Assertions --------------------------------------------------------------


@then("the savings report response status is {code:d}")
def step_then_status(context, code):
    res = context.last_response
    assert res.status_code == code, (
        f"expected {code}; got {res.status_code}: {res.text}"
    )


@then('the savings report has total_savings_kwh "{value}"')
def step_then_total_savings_kwh(context, value):
    body = context.last_response.json()
    assert str(body["total_savings_kwh"]) == value, (
        f"total_savings_kwh={body['total_savings_kwh']!r} expected {value!r}"
    )


@then('the savings report has total_savings_pct "{value}"')
def step_then_total_savings_pct(context, value):
    body = context.last_response.json()
    assert str(body["total_savings_pct"]) == value, (
        f"total_savings_pct={body['total_savings_pct']!r} expected {value!r}"
    )


@then('the savings report has total_baseline_kwh "{value}"')
def step_then_total_baseline_kwh(context, value):
    body = context.last_response.json()
    assert str(body["total_baseline_kwh"]) == value, (
        f"total_baseline_kwh={body['total_baseline_kwh']!r} expected {value!r}"
    )


@then('the savings report has total_actual_kwh "{value}"')
def step_then_total_actual_kwh(context, value):
    body = context.last_response.json()
    assert str(body["total_actual_kwh"]) == value, (
        f"total_actual_kwh={body['total_actual_kwh']!r} expected {value!r}"
    )


@then("the savings report total_savings_kwh equals the sum of per-line savings_kwh")
def step_then_totals_equal_sum_lines(context):
    body = context.last_response.json()
    total = Decimal(str(body["total_savings_kwh"]))
    line_sum = sum(
        (Decimal(str(ln["savings_kwh"])) for ln in body["lines"]),
        Decimal("0"),
    )
    assert total == line_sum, (
        f"total_savings_kwh={total} != sum_lines={line_sum}"
    )


@then(
    'the savings report line for zone "{zone_name}" of "{building_name}" '
    'has savings_kwh "{kwh}" and savings_pct "{pct}"'
)
def step_then_line_kwh_and_pct(
    context, zone_name, building_name, kwh, pct
):
    line = _line_for_zone(context, zone_name, building_name)
    assert str(line["savings_kwh"]) == kwh, (
        f"line.savings_kwh={line['savings_kwh']!r} expected {kwh!r}"
    )
    assert str(line["savings_pct"]) == pct, (
        f"line.savings_pct={line['savings_pct']!r} expected {pct!r}"
    )


@then(
    'the savings report line for zone "{zone_name}" of "{building_name}" '
    'has anomaly_flag "{flag}"'
)
def step_then_line_anomaly_flag(context, zone_name, building_name, flag):
    line = _line_for_zone(context, zone_name, building_name)
    expected = flag.lower() == "true"
    actual = bool(line["anomaly_flag"])
    assert actual == expected, (
        f"line.anomaly_flag={actual} expected {expected}; line={line}"
    )


@then(
    'the savings report line for zone "{zone_name}" of "{building_name}" '
    'has anomaly_reason "{reason}"'
)
def step_then_line_anomaly_reason(
    context, zone_name, building_name, reason
):
    line = _line_for_zone(context, zone_name, building_name)
    assert line["anomaly_reason"] == reason, (
        f"line.anomaly_reason={line['anomaly_reason']!r} expected {reason!r}"
    )


@then("the savings report response missingInputs equals {payload}")
def step_then_missing_inputs(context, payload):
    body = context.last_response.json()
    actual = body.get("detail", {}).get("missingInputs", [])
    expected = json.loads(payload)
    assert actual == expected, (
        f"missingInputs={actual} expected {expected}; full body={body}"
    )


@then('the savings report response has cached "{flag}"')
def step_then_cached(context, flag):
    body = context.last_response.json()
    expected = flag.lower() == "true"
    actual = bool(body.get("cached"))
    assert actual == expected, (
        f"cached={actual} expected {expected}; body={body}"
    )


@then("the savings report response elapsed_ms is under {limit_ms:d}")
def step_then_elapsed(context, limit_ms):
    body = context.last_response.json()
    elapsed = float(body.get("elapsed_ms", 0))
    assert elapsed < limit_ms, (
        f"elapsed_ms={elapsed} exceeds {limit_ms}"
    )


@then(
    'the database contains {n:d} daily_savings_reports row for '
    '"{building_name}" on "{date_str}"'
)
def step_then_header_count_singular(context, n, building_name, date_str):
    bid = _bid(context, building_name)
    actual = _count_headers(bid, date_str)
    assert actual == n, (
        f"expected {n} daily_savings_reports rows for ({bid}, {date_str}); "
        f"got {actual}"
    )


@then(
    'the database contains {n:d} daily_savings_reports rows for '
    '"{building_name}" on "{date_str}"'
)
def step_then_header_count_plural(context, n, building_name, date_str):
    bid = _bid(context, building_name)
    actual = _count_headers(bid, date_str)
    assert actual == n, (
        f"expected {n} daily_savings_reports rows for ({bid}, {date_str}); "
        f"got {actual}"
    )


@then(
    'the database contains {n:d} daily_savings_report_lines rows for '
    '"{building_name}" on "{date_str}"'
)
def step_then_line_count(context, n, building_name, date_str):
    bid = _bid(context, building_name)
    actual = _count_lines(bid, date_str)
    assert actual == n, (
        f"expected {n} daily_savings_report_lines for ({bid}, {date_str}); "
        f"got {actual}"
    )


# -- UI assertions -----------------------------------------------------------


@then("the SavingsReportPage shows the success banner")
def step_then_ui_success(context):
    context.page.wait_for_selector(
        '[data-testid="savings-success-banner"]', timeout=5_000
    )


@then('the SavingsReportPage shows totals for "{building_name}" on "{date_str}"')
def step_then_ui_totals(context, building_name, date_str):
    for tid in (
        "savings-total-baseline",
        "savings-total-actual",
        "savings-total-savings",
        "savings-total-pct",
    ):
        el = context.page.locator(f'[data-testid="{tid}"]')
        txt = el.inner_text().strip()
        assert txt, f"{tid} is empty"


@then('the SavingsReportPage shows a line row for zone "{zone_name}" of "{building_name}"')
def step_then_ui_line_row(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    context.page.wait_for_selector(
        f'[data-testid="savings-line-row-{zone_id}"]', timeout=5_000
    )


@then('the SavingsReportPage shows an anomaly flag for zone "{zone_name}" of "{building_name}"')
def step_then_ui_anomaly(context, zone_name, building_name):
    zones = _zones(context, building_name)
    zone_id = zones[zone_name]
    context.page.wait_for_selector(
        f'[data-testid="savings-anomaly-flag-{zone_id}"]', timeout=5_000
    )


@then("the SavingsReportPage shows the export button")
def step_then_ui_export(context):
    context.page.wait_for_selector(
        '[data-testid="savings-export-button"]', timeout=5_000
    )


@then("the SavingsReportPage shows the cached pill")
def step_then_ui_cached(context):
    context.page.wait_for_selector(
        '[data-testid="savings-cached-pill"]', timeout=5_000
    )
