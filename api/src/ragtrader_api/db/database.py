"""SQLAlchemy engine and session factories."""

from __future__ import annotations

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ragtrader_api.settings import ApiSettings, SettingsValidationError


def create_engine(settings: ApiSettings) -> Engine:
    """Create a SQLAlchemy engine using the configured Postgres DSN."""

    if settings.postgres_dsn is None:
        raise SettingsValidationError("Postgres DSN is required to create an engine.")

    engine = sa_create_engine(
        settings.postgres_dsn,
        pool_pre_ping=True,
        future=True,
    )
    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to the provided engine."""

    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


SessionFactory = sessionmaker[Session]


__all__ = ["create_engine", "session_factory", "SessionFactory"]
