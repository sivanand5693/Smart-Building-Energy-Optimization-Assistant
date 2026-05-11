import time

from behave import given, when, then
from sqlalchemy import create_engine, text

from app.core.config import settings


# -- Background --------------------------------------------------------------

@given("the FacilityManager is authenticated")
def step_authenticated(context):
    # Authentication is assumed via A3; no-op for UC1.
    context.authenticated = True


@given("the Building Repository is operational and empty")
def step_repo_empty(context):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM buildings")).scalar()
    engine.dispose()
    assert count == 0, f"Building Repository not empty: {count} rows"


# -- Actions -----------------------------------------------------------------

@when("I open the Register Building Profile form")
def step_open_form(context):
    context.page.goto(f"{context.frontend_url}/register-building")
    context.page.wait_for_selector('[data-testid="register-building-form"]')


@when('I enter building name "{name}"')
def step_enter_building_name(context, name):
    context.page.fill('[data-testid="building-name-input"]', name)


@when("I leave the building name empty")
def step_leave_name_empty(context):
    context.page.fill('[data-testid="building-name-input"]', "")


@when('I add zone "{zone_name}" with device type "{device_type}"')
def step_add_zone(context, zone_name, device_type):
    context.page.fill('[data-testid="zone-name-input"]', zone_name)
    context.page.select_option('[data-testid="device-type-input"]', device_type)
    context.page.click('[data-testid="add-zone-button"]')


@when("I add no zones")
def step_add_no_zones(context):
    pass


@when('I add operating schedule "{schedule_text}"')
def step_add_schedule(context, schedule_text):
    # Parses "Mon-Fri 08:00-18:00"
    days, times = schedule_text.rsplit(" ", 1)
    start, end = times.split("-")
    context.page.fill('[data-testid="schedule-days-input"]', days)
    context.page.fill('[data-testid="schedule-start-input"]', start)
    context.page.fill('[data-testid="schedule-end-input"]', end)
    context.page.click('[data-testid="add-schedule-button"]')


@when("I submit the form")
def step_submit(context):
    context.submit_start_ms = time.perf_counter() * 1000
    context.page.click('[data-testid="submit-button"]')
    # Wait for either confirmation or error to appear
    context.page.wait_for_function(
        """() => document.querySelector('[data-testid="confirmation-panel"]')
                || document.querySelector('[data-testid^="error-"]')
        """,
        timeout=10_000,
    )
    context.submit_end_ms = time.perf_counter() * 1000


# -- Assertions --------------------------------------------------------------

@then("a confirmation with a building ID is displayed")
def step_confirmation_visible(context):
    panel = context.page.locator('[data-testid="confirmation-panel"]')
    assert panel.is_visible(), "confirmation panel not visible"
    building_id = context.page.locator('[data-testid="building-id"]').inner_text()
    assert building_id.strip().isdigit(), f"building ID not numeric: {building_id!r}"


@then('the building "{name}" is saved in the Building Repository')
def step_building_saved(context, name):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, name FROM buildings WHERE name = :n"), {"n": name}
        ).first()
    engine.dispose()
    assert row is not None, f"building {name!r} not found in DB"
    context.saved_building_id = row[0]


@then('the saved building has zone "{zone_name}"')
def step_saved_building_has_zone(context, zone_name):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM zones WHERE building_id = :b AND name = :n"
            ),
            {"b": context.saved_building_id, "n": zone_name},
        ).first()
    engine.dispose()
    assert row is not None, f"zone {zone_name!r} not found"
    context.saved_zone_id = row[0]


@then('the saved zone has device type "{device_type}"')
def step_saved_zone_has_device(context, device_type):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM devices WHERE zone_id = :z AND device_type = :t"
            ),
            {"z": context.saved_zone_id, "t": device_type},
        ).first()
    engine.dispose()
    assert row is not None, f"device {device_type!r} not found for zone"


@then('the saved building has operating schedule "{schedule_text}"')
def step_saved_schedule(context, schedule_text):
    days, times = schedule_text.rsplit(" ", 1)
    start, end = times.split("-")
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM operating_schedules "
                "WHERE building_id = :b AND days_of_week = :d "
                "AND start_time = :s AND end_time = :e"
            ),
            {
                "b": context.saved_building_id,
                "d": days,
                "s": f"{start}:00",
                "e": f"{end}:00",
            },
        ).first()
    engine.dispose()
    assert row is not None, f"schedule {schedule_text!r} not found"


@then('a validation error for field "{field}" is displayed')
def step_validation_error_visible(context, field):
    selector = f'[data-testid="error-{field}"]'
    context.page.wait_for_selector(selector, timeout=5_000)
    text_content = context.page.locator(selector).inner_text()
    assert field in text_content, (
        f"error message for {field!r} did not name the field; got: {text_content!r}"
    )


@then("no building is saved in the Building Repository")
def step_no_building_saved(context):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM buildings")).scalar()
    engine.dispose()
    assert count == 0, f"expected 0 buildings saved; found {count}"


@then("the save time is under {limit_ms:d} milliseconds")
def step_save_time_under(context, limit_ms):
    elapsed = context.submit_end_ms - context.submit_start_ms
    assert elapsed < limit_ms, (
        f"save time {elapsed:.0f}ms exceeded limit {limit_ms}ms"
    )


# -- Expanded scenarios (S06–S17) -------------------------------------------

@when('I add zone "{zone_name}" with no device type')
def step_add_zone_no_device_type(context, zone_name):
    context.page.fill('[data-testid="zone-name-input"]', zone_name)
    context.page.select_option('[data-testid="device-type-input"]', "")
    context.page.click('[data-testid="add-zone-button"]')


@when("I add no operating schedule")
def step_add_no_schedule(context):
    pass


@when("I enter a building name of length {length:d}")
def step_enter_name_of_length(context, length):
    name = "B" * length
    context.long_building_name = name
    context.page.fill('[data-testid="building-name-input"]', name)


@then("the saved building has {n:d} zones")
def step_saved_building_has_n_zones(context, n):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM zones WHERE building_id = :b"),
            {"b": context.saved_building_id},
        ).scalar()
    engine.dispose()
    assert count == n, f"expected {n} zones; found {count}"


@then('the saved zone "{zone_name}" has device type "{device_type}"')
def step_saved_named_zone_has_device(context, zone_name, device_type):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT d.id FROM devices d "
                "JOIN zones z ON z.id = d.zone_id "
                "WHERE z.building_id = :b AND z.name = :n "
                "AND d.device_type = :t"
            ),
            {
                "b": context.saved_building_id,
                "n": zone_name,
                "t": device_type,
            },
        ).first()
    engine.dispose()
    assert row is not None, (
        f"device {device_type!r} not found for zone {zone_name!r}"
    )


@then("the saved building name has length {length:d}")
def step_saved_building_name_length(context, length):
    name = getattr(context, "long_building_name", None)
    assert name is not None, "no long building name recorded"
    assert len(name) == length, (
        f"recorded name length {len(name)} != expected {length}"
    )
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name FROM buildings WHERE name = :n"),
            {"n": name},
        ).first()
    engine.dispose()
    assert row is not None, "building with long name not found in DB"
    assert len(row[0]) == length, (
        f"DB name length {len(row[0])} != expected {length}"
    )


@then('the building name field still shows "{name}"')
def step_name_field_preserved(context, name):
    value = context.page.input_value('[data-testid="building-name-input"]')
    assert value == name, f"building name field shows {value!r}, expected {name!r}"


@then('the zones list still contains "{zone_name}"')
def step_zones_list_contains(context, zone_name):
    items = context.page.locator('[data-testid="zone-item"]').all_inner_texts()
    assert any(zone_name in t for t in items), (
        f"zones list does not contain {zone_name!r}; got {items!r}"
    )


@then('the Building Repository contains {n:d} buildings named "{name}"')
def step_repo_contains_n_named(context, n, name):
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id FROM buildings WHERE name = :n ORDER BY id"),
            {"n": name},
        ).fetchall()
    engine.dispose()
    assert len(rows) == n, f"expected {n} buildings named {name!r}; found {len(rows)}"
    context.saved_building_ids = [r[0] for r in rows]


@then("the two saved buildings have distinct IDs")
def step_two_distinct_ids(context):
    ids = getattr(context, "saved_building_ids", [])
    assert len(ids) == 2, f"expected 2 building IDs in context, got {ids!r}"
    assert ids[0] != ids[1], f"building IDs are not distinct: {ids!r}"


@then('the displayed building ID matches the ID of the saved building "{name}"')
def step_displayed_id_matches(context, name):
    displayed = context.page.locator('[data-testid="building-id"]').inner_text().strip()
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM buildings WHERE name = :n"),
            {"n": name},
        ).first()
    engine.dispose()
    assert row is not None, f"building {name!r} not found"
    assert displayed == str(row[0]), (
        f"displayed ID {displayed!r} does not match DB ID {row[0]!r}"
    )
