import time
from datetime import datetime, timedelta

from behave import given, when, then
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.models import BuildingModel, ZoneModel, DeviceModel


# -- Background --------------------------------------------------------------

@given('a building "{building_name}" exists with zones "{zone_a}" and "{zone_b}"')
def step_seed_building(context, building_name, zone_a, zone_b):
    engine = create_engine(settings.test_database_url, future=True)
    with Session(engine) as db:
        building = BuildingModel(name=building_name)
        for zone_name in (zone_a, zone_b):
            zone = ZoneModel(name=zone_name)
            zone.devices.append(DeviceModel(device_type="HVAC"))
            building.zones.append(zone)
        db.add(building)
        db.commit()
        db.refresh(building)
        context.building_id = building.id
        context.building_name = building.name
        context.zones = {z.name: z.id for z in building.zones}
    engine.dispose()


@given("the occupancy schedule store is empty")
def step_occupancy_empty(context):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM occupancy_records")
        ).scalar()
    engine.dispose()
    assert count == 0, f"occupancy_records not empty: {count}"


# -- Actions -----------------------------------------------------------------

@when("I open Import Occupancy Schedule")
def step_open_import(context):
    context.page.goto(f"{context.frontend_url}/import-occupancy")
    context.page.wait_for_selector('[data-testid="import-occupancy-form"]')
    # wait for buildings to load into dropdown
    context.page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="building-selector"] option').length > 0""",
        timeout=5_000,
    )


@when('I select building "{name}"')
def step_select_building(context, name):
    context.page.select_option(
        '[data-testid="building-selector"]', label=name
    )


def _attach_csv(context, content: str):
    context.page.set_input_files(
        '[data-testid="file-input"]',
        files=[
            {
                "name": "occupancy.csv",
                "mimeType": "text/csv",
                "buffer": content.encode("utf-8"),
            }
        ],
    )


def _rows_to_csv(context, rows: list[dict]) -> str:
    lines = ["zone_id,timestamp,occupancy_count"]
    for r in rows:
        zone_name = r["zone"]
        zone_id_val = context.zones.get(zone_name)
        # If the zone isn't registered in context, pass the raw text through
        # (useful only for diagnostics; real "unknown zone" tests use raw CSV)
        zone_field = zone_id_val if zone_id_val is not None else zone_name
        lines.append(f"{zone_field},{r['timestamp']},{r['occupancy_count']}")
    return "\n".join(lines) + "\n"


@when('I upload occupancy rows for building "{building_name}"')
@when('I upload occupancy rows for building "{building_name}" mixing valid and invalid')
def step_upload_rows_table(context, building_name):
    rows = [dict(row.as_dict()) for row in context.table]
    csv_content = _rows_to_csv(context, rows)
    _attach_csv(context, csv_content)


@when("I upload raw CSV content")
def step_upload_raw(context):
    _attach_csv(context, context.text or "")


@when("I upload an empty CSV")
def step_upload_empty(context):
    _attach_csv(context, "")


@when('I upload a generated CSV with {n:d} valid occupancy rows for building "{building_name}"')
def step_upload_generated(context, n, building_name):
    zone_ids = list(context.zones.values())
    assert zone_ids, "no zones seeded for generation"
    start = datetime(2026, 4, 20, 9, 0, 0)
    lines = ["zone_id,timestamp,occupancy_count"]
    for i in range(n):
        zone_id_val = zone_ids[i % len(zone_ids)]
        ts = start + timedelta(minutes=i)
        lines.append(f"{zone_id_val},{ts.isoformat()},{10 + (i % 20)}")
    _attach_csv(context, "\n".join(lines) + "\n")


@when("I submit the import")
def step_submit_import(context):
    context.submit_start_ms = time.perf_counter() * 1000
    context.page.click('[data-testid="submit-import-button"]')
    context.page.wait_for_function(
        """() => document.querySelector('[data-testid="import-confirmation"]')
                || document.querySelector('[data-testid="header-error"]')
                || document.querySelector('[data-testid="row-errors"]')
        """,
        timeout=30_000,
    )
    context.submit_end_ms = time.perf_counter() * 1000


# -- Assertions --------------------------------------------------------------

@then('a confirmation showing "{text_fragment}" is displayed')
def step_confirmation_text(context, text_fragment):
    panel = context.page.locator('[data-testid="import-confirmation"]')
    assert panel.is_visible(), "import confirmation not visible"
    content = context.page.locator('[data-testid="records-imported"]').inner_text()
    assert text_fragment in content, (
        f"expected {text_fragment!r} in confirmation; got {content!r}"
    )


@then("the occupancy schedule contains {n:d} records")
def step_occupancy_count(context, n):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM occupancy_records")
        ).scalar()
    engine.dispose()
    assert count == n, f"expected {n} records; got {count}"


@then('a record exists for zone "{zone_name}" at "{timestamp}" with count {count:d}')
def step_record_exists(context, zone_name, timestamp, count):
    zone_id_val = context.zones[zone_name]
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM occupancy_records "
                "WHERE zone_id = :z AND timestamp = :t AND occupancy_count = :c"
            ),
            {"z": zone_id_val, "t": timestamp, "c": count},
        ).first()
    engine.dispose()
    assert row is not None, (
        f"no occupancy_records row for zone={zone_name} ts={timestamp} count={count}"
    )


@then('an import error references row {row_num:d} and names the field "{field}"')
def step_row_error(context, row_num, field):
    selector = f'[data-testid="row-error-{row_num}"]'
    context.page.wait_for_selector(selector, timeout=5_000)
    txt = context.page.locator(selector).inner_text()
    assert str(row_num) in txt, f"row {row_num} not in error text: {txt!r}"
    assert field in txt, f"field {field!r} not in error text: {txt!r}"


@then("an import error indicates a header issue")
def step_header_error(context):
    panel = context.page.locator('[data-testid="header-error"]')
    panel.wait_for(timeout=5_000)
    assert panel.is_visible(), "header-error element not visible"
    text_content = panel.inner_text().lower()
    assert "header" in text_content or "expected" in text_content, (
        f"header-error text did not indicate a header issue: {text_content!r}"
    )


@then("an import error indicates the file is empty")
def step_empty_error(context):
    panel = context.page.locator('[data-testid="header-error"]')
    panel.wait_for(timeout=5_000)
    assert panel.is_visible(), "header-error element not visible"
    text_content = panel.inner_text().lower()
    assert "empty" in text_content, (
        f"empty-file error text did not mention 'empty': {text_content!r}"
    )


@then("the occupancy schedule is empty")
def step_occupancy_still_empty(context):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM occupancy_records")
        ).scalar()
    engine.dispose()
    assert count == 0, f"expected 0 records; found {count}"


@then("the import time is under {limit_ms:d} milliseconds")
def step_import_time(context, limit_ms):
    elapsed = context.submit_end_ms - context.submit_start_ms
    assert elapsed < limit_ms, (
        f"import time {elapsed:.0f}ms exceeded limit {limit_ms}ms"
    )
