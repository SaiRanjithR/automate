"""Database engine and session helpers (SQLite + SQLModel, migrations via Alembic)."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, event
from sqlmodel import Session, create_engine

from app.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=8)
def _engine_for(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


def get_engine(settings: Settings) -> Engine:
    url = settings.resolved_database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return _engine_for(url)


def run_migrations(settings: Settings) -> None:
    """Apply Alembic migrations up to head (idempotent)."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


def get_session(request: Request) -> Iterator[Session]:
    engine: Engine = request.app.state.engine
    with Session(engine) as session:
        yield session
