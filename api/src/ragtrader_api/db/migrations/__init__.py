"""Alembic migration runner utilities."""

from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING, Any, NoReturn, cast

_ALEMBIC_IMPORT_ERROR: ModuleNotFoundError | None

try:  # pragma: no cover - optional dependency guard
    from alembic import command as _alembic_command
    from alembic.config import Config as _AlembicConfig
except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency guard
    _ALEMBIC_IMPORT_ERROR = exc
    _alembic_command = cast(Any, None)

    def _raise_alembic_import_error() -> NoReturn:
        if _ALEMBIC_IMPORT_ERROR is None:  # pragma: no cover - sanity fallback
            raise ModuleNotFoundError("alembic must be installed")
        raise _ALEMBIC_IMPORT_ERROR

    class _MissingAlembicConfig:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _raise_alembic_import_error()

    _ConfigFactory = cast(type[Any], _MissingAlembicConfig)
else:
    _ALEMBIC_IMPORT_ERROR = None
    _ConfigFactory = cast(type[Any], _AlembicConfig)

Config = _ConfigFactory

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from sqlalchemy.engine import Engine
else:  # pragma: no cover - fallback type to keep runtime dependency optional
    Engine = Any


def _script_location() -> str:
    return str(resources.files(__name__))


def apply_migrations(engine: Engine, revision: str = "head") -> None:
    """Apply Alembic migrations to the provided engine."""

    if _alembic_command is None:
        msg = "alembic must be installed to run database migrations"
        raise ModuleNotFoundError(msg) from _ALEMBIC_IMPORT_ERROR

    config = Config()
    config.set_main_option("sqlalchemy.url", str(engine.url))
    config.set_main_option("script_location", _script_location())
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        _alembic_command.upgrade(config, revision)


__all__ = ["apply_migrations"]
