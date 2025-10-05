"""Alembic migration runner utilities."""

from __future__ import annotations

from importlib import resources

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine


def _script_location() -> str:
    return str(resources.files(__name__))


def apply_migrations(engine: Engine, revision: str = "head") -> None:
    """Apply Alembic migrations to the provided engine."""

    config = Config()
    config.set_main_option("sqlalchemy.url", str(engine.url))
    config.set_main_option("script_location", _script_location())
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


__all__ = ["apply_migrations"]
