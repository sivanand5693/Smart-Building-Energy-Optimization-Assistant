import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


def _resolve_database_url() -> str:
    if os.getenv("TESTING") == "1":
        return settings.test_database_url
    return settings.database_url


engine = create_engine(_resolve_database_url(), future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass
