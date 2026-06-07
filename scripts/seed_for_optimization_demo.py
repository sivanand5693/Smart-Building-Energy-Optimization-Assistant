"""Seed smart_building_dev with UC1+UC2 outputs so a live demo can start at UC3.

Run BEFORE Group B demo. Backend must be running with:
    TESTING=1 TEST_DATABASE_URL="postgresql://localhost/smart_building_dev" \
        uvicorn app.main:app --reload --port 8000

so the forecast / optimization / device-control test doubles are wired and the
test-support endpoints are mounted at /api/_test.

Inserts:
  * 1 building (Demo Tower)
  * 3 zones (Zone-A, Zone-B, Zone-C)
  * 1 HVAC device per zone
  * 1 operating schedule
  * 12 occupancy records (4 timestamps x 3 zones)
  * Comfort constraints per zone
Then seeds the weather + device_state doubles via the test-support API.
"""
from __future__ import annotations

import sys
from datetime import datetime, time, timedelta

import httpx
import psycopg2

DB_URL = "postgresql://localhost/smart_building_dev"
API_BASE = "http://localhost:8000"


TABLES_IN_TRUNCATE_ORDER = [
    "sensor_outage_events",
    "daily_savings_report_lines",
    "daily_savings_reports",
    "energy_usage_records",
    "recommendation_explanations",
    "comfort_risk_alerts",
    "comfort_risk_runs",
    "plan_adaptation_events",
    "applied_setpoint_changes",
    "setpoint_recommendations",
    "zone_comfort_constraints",
    "demand_forecasts",
    "occupancy_records",
    "operating_schedules",
    "devices",
    "zones",
    "buildings",
]


def truncate(cur) -> None:
    cur.execute(
        f"TRUNCATE {', '.join(TABLES_IN_TRUNCATE_ORDER)} RESTART IDENTITY CASCADE"
    )


def seed_db(cur) -> tuple[int, list[int]]:
    cur.execute(
        "INSERT INTO buildings (name) VALUES (%s) RETURNING id",
        ("Demo Tower",),
    )
    building_id = cur.fetchone()[0]

    zone_ids: list[int] = []
    for zone_name in ("Zone-A", "Zone-B", "Zone-C"):
        cur.execute(
            "INSERT INTO zones (building_id, name) VALUES (%s, %s) RETURNING id",
            (building_id, zone_name),
        )
        zone_ids.append(cur.fetchone()[0])

    for zid in zone_ids:
        cur.execute(
            "INSERT INTO devices (zone_id, device_type, device_name) "
            "VALUES (%s, 'HVAC', %s)",
            (zid, f"HVAC-{zid}"),
        )

    cur.execute(
        "INSERT INTO operating_schedules (building_id, days_of_week, start_time, end_time) "
        "VALUES (%s, %s, %s, %s)",
        (building_id, "Mon-Fri", time(8, 0), time(18, 0)),
    )

    base = datetime(2026, 6, 1, 9, 0)
    for zid in zone_ids:
        for hour in range(4):
            ts = base + timedelta(hours=hour)
            count = 10 + hour * 5 + (zid % 3)
            cur.execute(
                "INSERT INTO occupancy_records (zone_id, timestamp, occupancy_count) "
                "VALUES (%s, %s, %s)",
                (zid, ts, count),
            )

    for zid in zone_ids:
        cur.execute(
            "INSERT INTO zone_comfort_constraints "
            "(zone_id, min_setpoint_f, max_setpoint_f, "
            " occupied_min_f, occupied_max_f, unoccupied_min_f, unoccupied_max_f) "
            "VALUES (%s, 65.0, 78.0, 68.0, 75.0, 65.0, 78.0)",
            (zid,),
        )

    # UC9 baseline + actual energy usage for a fixed reporting day
    report_date = "2026-06-01"
    for zid in zone_ids:
        cur.execute(
            "INSERT INTO energy_usage_records "
            "(building_id, zone_id, usage_date, kind, kwh) "
            "VALUES (%s, %s, %s, 'baseline', %s)",
            (building_id, zid, report_date, 100.0),
        )
        cur.execute(
            "INSERT INTO energy_usage_records "
            "(building_id, zone_id, usage_date, kind, kwh) "
            "VALUES (%s, %s, %s, 'actual', %s)",
            (building_id, zid, report_date, 80.0),
        )

    return building_id, zone_ids


def seed_adapter_doubles(building_id: int, zone_ids: list[int]) -> None:
    with httpx.Client(base_url=API_BASE, timeout=5.0) as client:
        client.post("/api/_test/forecast_doubles/reset")
        client.post(
            "/api/_test/forecast_doubles",
            json={
                "kind": "weather",
                "building_id": building_id,
                "payload": {"temperature_f": 78.0, "humidity": 0.55},
            },
        )
        for zid in zone_ids:
            client.post(
                "/api/_test/forecast_doubles",
                json={
                    "kind": "device_state",
                    "zone_id": zid,
                    "payload": {"setpoint_f": 72.0, "mode": "cool"},
                },
            )


def main() -> int:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            truncate(cur)
            building_id, zone_ids = seed_db(cur)
        conn.commit()
    finally:
        conn.close()

    try:
        seed_adapter_doubles(building_id, zone_ids)
    except httpx.HTTPError as exc:
        print(
            f"WARNING: could not seed adapter doubles ({exc}).\n"
            "Is the backend running with TESTING=1?",
            file=sys.stderr,
        )
        return 2

    print("Seed complete.")
    print(f"  building_id = {building_id}")
    print(f"  zone_ids    = {zone_ids}")
    print("  energy_usage_records seeded for 2026-06-01 (baseline=100, actual=80 per zone)")
    print("Next: open http://localhost:5173/forecasts and click Run Forecast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
