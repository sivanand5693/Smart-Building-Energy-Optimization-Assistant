from sqlalchemy import create_engine, text

from app.core.config import settings


def reset_test_database() -> None:
    engine = create_engine(settings.test_database_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE operating_schedules, devices, zones, buildings "
                "RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()
