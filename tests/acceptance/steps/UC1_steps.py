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
