"""Regression tests for the database CLI helpers."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError


class _FakeEngine:
    """Simple stand-in for a SQLAlchemy engine used in the tests."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.disposed: list[str] = []

    def dispose(self) -> None:  # pragma: no cover - simple recorder
        self.disposed.append(self.label)


def test_main_retries_with_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI retries migrations with localhost after a DNS error."""

    from ragtrader_api.db import __main__ as db_main

    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql://user:pass@postgres:5432/app",
    )

    def dns_error() -> OperationalError:
        return OperationalError(
            "connect",  # statement
            None,  # params
            OSError(-3, "Temporary failure in name resolution"),
        )

    sa_calls: list[str] = []
    initial_engine = _FakeEngine("initial")
    created_retry_engine = _FakeEngine("retry")
    migration_engines: list[_FakeEngine] = []

    def fake_sa_create_engine(dsn: str, **_: Any) -> _FakeEngine:
        sa_calls.append(dsn)
        if len(sa_calls) == 1:
            raise dns_error()
        return created_retry_engine

    def fake_create_engine(settings: Any) -> _FakeEngine:
        try:
            db_main.database.sa_create_engine(
                settings.postgres_dsn,
                pool_pre_ping=True,
                future=True,
            )
        except OperationalError:
            pass
        return initial_engine

    def fake_apply_migrations(engine: _FakeEngine) -> None:
        migration_engines.append(engine)
        if len(migration_engines) == 1:
            raise dns_error()

    monkeypatch.setattr(db_main.database, "sa_create_engine", fake_sa_create_engine)
    monkeypatch.setattr(db_main.database, "create_engine", fake_create_engine)
    monkeypatch.setattr(db_main.migrations, "apply_migrations", fake_apply_migrations)

    db_main.main()

    assert len(sa_calls) == 2
    retry_url = make_url(sa_calls[1])
    assert retry_url.host == "localhost"

    assert len(migration_engines) == 2
    assert migration_engines[1] is created_retry_engine
    assert migration_engines[0] is initial_engine
    assert initial_engine.disposed == ["initial"]
    assert created_retry_engine.disposed == ["retry"]


def test_main_retries_without_vector_store_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI can retry migrations without requiring Qdrant settings."""

    from ragtrader_api.db import __main__ as db_main

    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql://user:pass@postgres:5432/app",
    )
    monkeypatch.delenv("RAGTRADER_API_USE_QDRANT_CLOUD", raising=False)
    monkeypatch.delenv("RAGTRADER_API_REQUIRE_VECTOR_STORE", raising=False)

    sa_calls: list[str] = []
    migration_engines: list[_FakeEngine] = []
    initial_engine = _FakeEngine("initial")
    retry_engine = _FakeEngine("retry")

    def dns_error() -> OperationalError:
        return OperationalError(
            "connect",  # statement
            None,  # params
            OSError(-3, "Temporary failure in name resolution"),
        )

    def fake_sa_create_engine(dsn: str, **_: Any) -> _FakeEngine:
        sa_calls.append(dsn)
        if len(sa_calls) == 1:
            raise dns_error()
        return retry_engine

    def fake_create_engine(settings: Any) -> _FakeEngine:
        try:
            db_main.database.sa_create_engine(
                settings.postgres_dsn,
                pool_pre_ping=True,
                future=True,
            )
        except OperationalError:
            pass
        return initial_engine

    def fake_apply_migrations(engine: _FakeEngine) -> None:
        migration_engines.append(engine)
        if len(migration_engines) == 1:
            raise dns_error()

    monkeypatch.setattr(db_main.database, "sa_create_engine", fake_sa_create_engine)
    monkeypatch.setattr(db_main.database, "create_engine", fake_create_engine)
    monkeypatch.setattr(db_main.migrations, "apply_migrations", fake_apply_migrations)

    db_main.main()

    assert len(sa_calls) == 2
    retry_url = make_url(sa_calls[1])
    assert retry_url.host == "localhost"
    assert len(migration_engines) == 2
    assert migration_engines[0] is initial_engine
    assert migration_engines[1] is retry_engine
