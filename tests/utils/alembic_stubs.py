"""Helpers that provide lightweight Alembic/SQLAlchemy stand-ins for tests."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

__all__ = ["ensure_alembic_sqlalchemy_stubs"]


def ensure_alembic_sqlalchemy_stubs() -> dict[str, ModuleType]:
    """Ensure Alembic and SQLAlchemy modules are importable during tests.

    Returns a mapping of module names to the module objects that were prepared.
    """

    default_config = type(
        "DefaultAlembicConfig",
        (),
        {
            "config_file_name": None,
            "config_ini_section": "alembic",
            "attributes": {},
            "get_main_option": staticmethod(lambda _key: ""),
            "get_section": staticmethod(lambda _section: {}),
        },
    )()

    def _default_begin_transaction():
        class _Transaction:
            def __enter__(self) -> _Transaction:  # type: ignore[name-defined]
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        return _Transaction()

    alembic_context_stub = ModuleType("alembic.context")
    alembic_context_stub.config = default_config  # type: ignore[attr-defined]
    alembic_context_stub.configure = lambda **_kwargs: None  # type: ignore[attr-defined]
    alembic_context_stub.begin_transaction = _default_begin_transaction  # type: ignore[attr-defined]
    alembic_context_stub.run_migrations = lambda: None  # type: ignore[attr-defined]
    alembic_context_stub.is_offline_mode = lambda: True  # type: ignore[attr-defined]

    alembic_command_stub = ModuleType("alembic.command")
    alembic_command_stub.upgrade = lambda *_, **__: None  # type: ignore[attr-defined]

    try:  # pragma: no cover - exercised only when Alembic is available
        alembic_module = importlib.import_module("alembic")
    except ModuleNotFoundError:  # pragma: no cover - executed in pared-down test env
        alembic_module = ModuleType("alembic")
        sys.modules.setdefault("alembic", alembic_module)
    else:
        sys.modules["alembic"] = alembic_module

    try:  # pragma: no cover - exercised only when Alembic is available
        alembic_context_module = importlib.import_module("alembic.context")
    except ModuleNotFoundError:  # pragma: no cover - executed in pared-down test env
        alembic_context_module = alembic_context_stub
        sys.modules.setdefault("alembic.context", alembic_context_stub)
    else:
        _required_context_attrs = (
            "config",
            "configure",
            "begin_transaction",
            "run_migrations",
            "is_offline_mode",
        )
        if not all(
            hasattr(alembic_context_module, attr) for attr in _required_context_attrs
        ):
            sys.modules["alembic.context"] = alembic_context_stub
            alembic_context_module = alembic_context_stub

    try:  # pragma: no cover - exercised only when Alembic is available
        alembic_command_module = importlib.import_module("alembic.command")
    except ModuleNotFoundError:  # pragma: no cover - executed in pared-down test env
        alembic_command_module = alembic_command_stub
        sys.modules.setdefault("alembic.command", alembic_command_stub)
    else:
        if not hasattr(alembic_command_module, "upgrade"):
            sys.modules["alembic.command"] = alembic_command_stub
            alembic_command_module = alembic_command_stub

    if not hasattr(alembic_module, "context"):
        alembic_module.context = alembic_context_module  # type: ignore[attr-defined]

    if not hasattr(alembic_module, "command"):
        alembic_module.command = alembic_command_module  # type: ignore[attr-defined]

    try:  # pragma: no cover - exercised only when SQLAlchemy is available
        sqlalchemy_module = importlib.import_module("sqlalchemy")
    except ModuleNotFoundError:  # pragma: no cover - executed in pared-down test env
        sqlalchemy_pool_module = ModuleType("sqlalchemy.pool")
        sqlalchemy_pool_module.NullPool = object()  # type: ignore[attr-defined]

        sqlalchemy_engine_module = ModuleType("sqlalchemy.engine")
        sqlalchemy_engine_module.Engine = object  # type: ignore[attr-defined]

        class _SessionmakerFactory:
            def __getitem__(self, _item):
                return self

            def __call__(self, *args, **kwargs):
                return None

        def _placeholder(*_args, **_kwargs):
            return None

        class _DeclarativeBase:
            metadata = object()

        class _Mapped:
            def __class_getitem__(cls, _item):
                return cls

        sqlalchemy_orm_module = ModuleType("sqlalchemy.orm")
        sqlalchemy_orm_module.DeclarativeBase = _DeclarativeBase  # type: ignore[attr-defined]
        sqlalchemy_orm_module.Mapped = _Mapped  # type: ignore[attr-defined]
        sqlalchemy_orm_module.Session = type("Session", (), {})  # type: ignore[attr-defined]
        sqlalchemy_orm_module.mapped_column = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_orm_module.relationship = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_orm_module.sessionmaker = _SessionmakerFactory()  # type: ignore[attr-defined]

        sqlalchemy_module = ModuleType("sqlalchemy")

        sqlalchemy_module.engine_from_config = lambda *_, **__: None  # type: ignore[attr-defined]
        sqlalchemy_module.create_engine = lambda *_, **__: None  # type: ignore[attr-defined]
        sqlalchemy_module.pool = sqlalchemy_pool_module  # type: ignore[attr-defined]
        sqlalchemy_module.engine = sqlalchemy_engine_module  # type: ignore[attr-defined]
        sqlalchemy_module.orm = sqlalchemy_orm_module  # type: ignore[attr-defined]
        sqlalchemy_module.DateTime = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_module.ForeignKey = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_module.Index = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_module.Numeric = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_module.String = _placeholder  # type: ignore[attr-defined]
        sqlalchemy_module.text = lambda clause: clause  # type: ignore[attr-defined]

        sys.modules.setdefault("sqlalchemy", sqlalchemy_module)
        sys.modules.setdefault("sqlalchemy.pool", sqlalchemy_pool_module)
        sys.modules.setdefault("sqlalchemy.engine", sqlalchemy_engine_module)
        sys.modules.setdefault("sqlalchemy.orm", sqlalchemy_orm_module)
    else:
        # Ensure submodules are discoverable when SQLAlchemy is present.
        for submodule in ("sqlalchemy.pool", "sqlalchemy.engine", "sqlalchemy.orm"):
            try:
                importlib.import_module(submodule)
            except ModuleNotFoundError:  # pragma: no cover
                # These modules should exist when SQLAlchemy is installed.
                pass

    return {
        "alembic": alembic_module,
        "alembic.context": alembic_context_module,
        "alembic.command": alembic_command_module,
        "sqlalchemy": sqlalchemy_module,
    }
