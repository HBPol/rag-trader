"""Tests for the ``ragtrader_api.db.__main__`` module."""

from __future__ import annotations

import importlib
import sys
import types


def test_main_invokes_dependencies_in_order(monkeypatch) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    settings_sentinel = object()
    engine_sentinel = object()

    def _stub_type(name: str) -> type:
        return type(
            name,
            (),
            {"__init__": lambda self, *args, **kwargs: None},
        )

    fake_sqlalchemy = types.ModuleType("sqlalchemy")
    fake_sqlalchemy.create_engine = lambda *args, **kwargs: None  # pragma: no cover - stub
    fake_sqlalchemy.DateTime = _stub_type("DateTime")
    fake_sqlalchemy.ForeignKey = _stub_type("ForeignKey")
    fake_sqlalchemy.Index = _stub_type("Index")
    fake_sqlalchemy.Numeric = _stub_type("Numeric")
    fake_sqlalchemy.String = _stub_type("String")
    fake_sqlalchemy.text = lambda *args, **kwargs: None  # pragma: no cover - stub

    fake_sqlalchemy_engine = types.ModuleType("sqlalchemy.engine")
    fake_sqlalchemy_engine.Engine = type("Engine", (), {})

    fake_sqlalchemy_orm = types.ModuleType("sqlalchemy.orm")

    class FakeSession:  # pragma: no cover - stub
        pass

    class FakeDeclarativeBase:  # pragma: no cover - stub
        pass

    class FakeMapped:
        @classmethod
        def __class_getitem__(cls, _item):  # pragma: no cover - stub
            return cls

    def fake_mapped_column(*args, **kwargs) -> object:  # pragma: no cover - stub
        return object()

    def fake_relationship(*args, **kwargs) -> object:  # pragma: no cover - stub
        return object()

    class FakeSessionmaker:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - stub
            pass

        def __call__(self, *args, **kwargs) -> object:  # pragma: no cover - stub
            return object()

        @classmethod
        def __class_getitem__(cls, _item):  # pragma: no cover - stub
            return cls

    fake_sqlalchemy_orm.Session = FakeSession
    fake_sqlalchemy_orm.DeclarativeBase = FakeDeclarativeBase
    fake_sqlalchemy_orm.Mapped = FakeMapped
    fake_sqlalchemy_orm.mapped_column = fake_mapped_column
    fake_sqlalchemy_orm.relationship = fake_relationship
    fake_sqlalchemy_orm.sessionmaker = FakeSessionmaker

    monkeypatch.setitem(sys.modules, "sqlalchemy", fake_sqlalchemy)
    monkeypatch.setitem(sys.modules, "sqlalchemy.engine", fake_sqlalchemy_engine)
    monkeypatch.setitem(sys.modules, "sqlalchemy.orm", fake_sqlalchemy_orm)

    db_main = importlib.import_module("ragtrader_api.db.__main__")

    def fake_get_settings() -> object:
        calls.append(("get_settings", ()))
        return settings_sentinel

    def fake_create_engine(received_settings: object) -> object:
        calls.append(("create_engine", (received_settings,)))
        assert received_settings is settings_sentinel
        return engine_sentinel

    def fake_apply_migrations(received_engine: object) -> None:
        calls.append(("apply_migrations", (received_engine,)))
        assert received_engine is engine_sentinel

    monkeypatch.setattr(db_main, "get_settings", fake_get_settings)
    monkeypatch.setattr(db_main.database, "create_engine", fake_create_engine)
    monkeypatch.setattr(db_main.migrations, "apply_migrations", fake_apply_migrations)

    db_main.main()

    assert calls == [
        ("get_settings", ()),
        ("create_engine", (settings_sentinel,)),
        ("apply_migrations", (engine_sentinel,)),
    ]

    monkeypatch.undo()
