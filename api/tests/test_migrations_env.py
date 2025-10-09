"""Tests for the Alembic environment helpers."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Ensure the application sources are importable when running the tests standalone.
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Provide lightweight stand-ins for optional dependencies that may not be installed
# in the unit-test environment.
try:  # pragma: no cover - exercised only when Alembic is available
    importlib.import_module("alembic")
except ModuleNotFoundError:  # pragma: no cover - executed in the pared-down test env
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
            def __enter__(self) -> "_Transaction":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        return _Transaction()

    alembic_context = ModuleType("alembic.context")
    alembic_context.config = default_config
    alembic_context.configure = lambda **_kwargs: None
    alembic_context.begin_transaction = _default_begin_transaction
    alembic_context.run_migrations = lambda: None
    alembic_context.is_offline_mode = lambda: True

    alembic_command = ModuleType("alembic.command")
    alembic_command.upgrade = lambda *_, **__: None

    alembic_module = ModuleType("alembic")
    alembic_module.context = alembic_context
    alembic_module.command = alembic_command

    sys.modules.setdefault("alembic", alembic_module)
    sys.modules.setdefault("alembic.context", alembic_context)
    sys.modules.setdefault("alembic.command", alembic_command)

try:  # pragma: no cover - exercised only when SQLAlchemy is available
    importlib.import_module("sqlalchemy")
except ModuleNotFoundError:  # pragma: no cover - executed in the pared-down test env
    sqlalchemy_pool_module = ModuleType("sqlalchemy.pool")
    sqlalchemy_pool_module.NullPool = object()

    sqlalchemy_engine_module = ModuleType("sqlalchemy.engine")
    sqlalchemy_engine_module.Engine = object

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
    sqlalchemy_orm_module.DeclarativeBase = _DeclarativeBase
    sqlalchemy_orm_module.Mapped = _Mapped
    sqlalchemy_orm_module.Session = type("Session", (), {})
    sqlalchemy_orm_module.mapped_column = _placeholder
    sqlalchemy_orm_module.relationship = _placeholder
    sqlalchemy_orm_module.sessionmaker = _SessionmakerFactory()

    sqlalchemy_module = ModuleType("sqlalchemy")

    sqlalchemy_module.engine_from_config = lambda *_, **__: None
    sqlalchemy_module.create_engine = lambda *_, **__: None
    sqlalchemy_module.pool = sqlalchemy_pool_module
    sqlalchemy_module.engine = sqlalchemy_engine_module
    sqlalchemy_module.orm = sqlalchemy_orm_module
    sqlalchemy_module.DateTime = _placeholder
    sqlalchemy_module.ForeignKey = _placeholder
    sqlalchemy_module.Index = _placeholder
    sqlalchemy_module.Numeric = _placeholder
    sqlalchemy_module.String = _placeholder
    sqlalchemy_module.text = lambda clause: clause

    sys.modules.setdefault("sqlalchemy", sqlalchemy_module)
    sys.modules.setdefault("sqlalchemy.pool", sqlalchemy_pool_module)
    sys.modules.setdefault("sqlalchemy.engine", sqlalchemy_engine_module)
    sys.modules.setdefault("sqlalchemy.orm", sqlalchemy_orm_module)

import ragtrader_api.db.migrations.env as env_module


class ConfigStub:
    """Captures configuration interactions made by the Alembic environment."""

    def __init__(
        self,
        *,
        url: str = "sqlite:///memory",
        section: dict[str, object] | None = None,
        attributes: dict[str, object] | None = None,
    ) -> None:
        self.url = url
        self.section = section if section is not None else {}
        self.attributes = dict(attributes or {})
        self.config_file_name: str | None = None
        self.config_ini_section = "alembic"
        self.main_option_requests: list[str] = []
        self.get_section_requests: list[str] = []

    def get_main_option(self, key: str) -> str:
        self.main_option_requests.append(key)
        if key == "sqlalchemy.url":
            return self.url
        raise KeyError(key)

    def get_section(self, name: str) -> dict[str, object]:
        self.get_section_requests.append(name)
        return self.section


class BaseContextStub:
    """Base implementation shared by the online/offline context stubs."""

    def __init__(self, config: ConfigStub) -> None:
        self.config = config
        self.configure_calls: list[dict[str, object]] = []
        self.transactions_started = 0
        self.transactions_ended = 0
        self.migrations_ran = 0

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)

    def begin_transaction(self):  # type: ignore[override]
        self.transactions_started += 1
        parent = self

        class _Transaction:
            def __enter__(self_inner) -> "_Transaction":
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb) -> bool:
                parent.transactions_ended += 1
                return False

        return _Transaction()

    def run_migrations(self) -> None:
        self.migrations_ran += 1


class OfflineContextStub(BaseContextStub):
    def is_offline_mode(self) -> bool:
        return True


class OnlineContextStub(BaseContextStub):
    def is_offline_mode(self) -> bool:
        return False


class ConnectionStub:
    def __init__(self) -> None:
        self.closed = False


class EngineStub:
    def __init__(self, connection: ConnectionStub) -> None:
        self.connection = connection
        self.connect_calls = 0

    def connect(self):  # type: ignore[override]
        engine = self

        class _ConnectionContext:
            def __enter__(self_inner) -> ConnectionStub:
                engine.connect_calls += 1
                return engine.connection

            def __exit__(self_inner, exc_type, exc, tb) -> bool:
                engine.connection.closed = True
                return False

        return _ConnectionContext()


class EngineFactoryStub:
    def __init__(self, engine: EngineStub) -> None:
        self.engine = engine
        self.calls: list[dict[str, object]] = []

    def __call__(self, config: dict[str, object], *, prefix: str, poolclass: object) -> EngineStub:
        self.calls.append({"config": config, "prefix": prefix, "poolclass": poolclass})
        return self.engine


def test_run_migrations_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    config = ConfigStub(url="sqlite:///offline.db")
    context = OfflineContextStub(config)

    monkeypatch.setattr(env_module, "context", context)
    monkeypatch.setattr(env_module, "config", context.config)

    env_module.run_migrations()

    assert config.main_option_requests == ["sqlalchemy.url"]
    assert context.configure_calls == [
        {
            "url": config.url,
            "target_metadata": env_module.target_metadata,
            "literal_binds": True,
            "dialect_opts": {"paramstyle": "named"},
        }
    ]
    assert context.transactions_started == 1
    assert context.transactions_ended == 1
    assert context.migrations_ran == 1


def test_run_migrations_online_creates_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    config = ConfigStub(
        url="sqlite:///online.db",
        section={"sqlalchemy.url": "sqlite:///online.db"},
    )
    context = OnlineContextStub(config)
    connection = ConnectionStub()
    engine = EngineStub(connection)
    engine_factory = EngineFactoryStub(engine)
    sentinel_pool = object()

    monkeypatch.setattr(env_module, "context", context)
    monkeypatch.setattr(env_module, "config", context.config)
    monkeypatch.setattr(env_module, "engine_from_config", engine_factory)
    monkeypatch.setattr(env_module.pool, "NullPool", sentinel_pool)

    env_module.run_migrations()

    assert config.get_section_requests == [config.config_ini_section]
    assert engine_factory.calls == [
        {"config": config.section, "prefix": "sqlalchemy.", "poolclass": sentinel_pool}
    ]
    assert engine.connect_calls == 1
    assert connection.closed is True
    assert context.configure_calls == [
        {"connection": connection, "target_metadata": env_module.target_metadata}
    ]
    assert context.transactions_started == 1
    assert context.transactions_ended == 1
    assert context.migrations_ran == 1


def test_run_migrations_online_reuses_existing_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    existing_connection = object()
    config = ConfigStub(attributes={"connection": existing_connection})
    context = OnlineContextStub(config)

    def _unexpected_engine_factory(*_args, **_kwargs):  # pragma: no cover - sanity guard
        raise AssertionError("engine_from_config should not be invoked when a connection exists")

    monkeypatch.setattr(env_module, "context", context)
    monkeypatch.setattr(env_module, "config", context.config)
    monkeypatch.setattr(env_module, "engine_from_config", _unexpected_engine_factory)

    env_module.run_migrations()

    assert config.get_section_requests == []
    assert context.configure_calls == [
        {"connection": existing_connection, "target_metadata": env_module.target_metadata}
    ]
    assert context.transactions_started == 1
    assert context.transactions_ended == 1
    assert context.migrations_ran == 1
