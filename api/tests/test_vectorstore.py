"""Contract tests for the Qdrant vector store repository."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any
from unittest.mock import Mock

import pytest

from ragtrader_api.settings import ApiSettings
from ragtrader_api.vectorstore import QdrantClientProtocol, VectorStoreRepository


def _settings(**overrides: Any) -> ApiSettings:
    base_kwargs: dict[str, Any] = {
        "postgres_dsn": "postgresql+psycopg://user:pass@localhost:5432/app",
        "qdrant_url": "https://example-qdrant",
        "qdrant_api_key": "secret",
        "require_database": False,
        "require_vector_store": True,
        "use_qdrant_cloud": True,
    }
    base_kwargs.update(overrides)
    return ApiSettings(**base_kwargs)


def test_repository_uses_cloud_credentials_when_flag_enabled() -> None:
    captured_kwargs: dict[str, Any] = {}

    def _factory(**kwargs: Any) -> Mock:
        captured_kwargs.update(kwargs)
        client = Mock()
        client.create_collection.return_value = {"collection": kwargs["url"]}
        return client

    repo = VectorStoreRepository(_settings(), client_factory=_factory)
    response = repo.create_collection("demo", vectors_config={"size": 3})

    assert response == {"collection": "https://example-qdrant"}
    assert captured_kwargs["url"] == "https://example-qdrant"
    assert captured_kwargs["api_key"] == "secret"


def test_repository_omits_api_key_for_self_hosted() -> None:
    captured_kwargs: dict[str, Any] = {}

    def _factory(**kwargs: Any) -> Mock:
        captured_kwargs.update(kwargs)
        client = Mock()
        client.delete_collection.return_value = True
        return client

    repo = VectorStoreRepository(
        _settings(use_qdrant_cloud=False),
        client_factory=_factory,
    )

    assert repo.delete_collection("demo") is True
    assert captured_kwargs["url"] == "https://example-qdrant"
    assert "api_key" not in captured_kwargs


def test_repository_requires_positive_retry_attempts() -> None:
    with pytest.raises(ValueError):
        VectorStoreRepository(_settings(), retry_attempts=0)


def test_repository_warns_when_cloud_without_key(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}

    def _factory(**kwargs: Any) -> Mock:
        captured_kwargs.update(kwargs)
        client = Mock()
        client.delete_collection.return_value = True
        return client

    monkeypatch.delenv("RAGTRADER_API_QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    settings = _settings(
        qdrant_api_key=None,
        require_vector_store=False,
        use_qdrant_cloud=True,
    )

    repo = VectorStoreRepository(settings, client_factory=_factory)

    with caplog.at_level(logging.WARNING):
        assert repo.delete_collection("demo") is True

    assert any(
        "no API key provided" in message for message in caplog.messages
    ), "Expected warning about missing API key"
    assert captured_kwargs["url"] == "https://example-qdrant"
    assert "api_key" not in captured_kwargs


def test_repository_defaults_collection_from_settings() -> None:
    captured_kwargs: dict[str, Any] = {}
    client = Mock()
    client.create_collection.return_value = {"collection": "ok"}

    def _factory(**kwargs: Any) -> Mock:
        captured_kwargs.update(kwargs)
        return client

    repo = VectorStoreRepository(
        _settings(qdrant_collection="docs"),
        client_factory=_factory,
    )

    repo.create_collection(None, vectors_config={"size": 3})

    assert captured_kwargs["url"] == "https://example-qdrant"
    client.create_collection.assert_called_once_with(
        collection_name="docs", vectors_config={"size": 3}
    )


def test_repository_close_calls_client_close_and_clears_reference() -> None:
    class _Client(QdrantClientProtocol):
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:  # type: ignore[override]
            self.closed += 1

        def create_collection(self, *args: Any, **kwargs: Any) -> Any:
            return {"collection": kwargs.get("collection_name")}

        def upsert(self, *args: Any, **kwargs: Any) -> Any:
            return "ok"

        def delete(self, *args: Any, **kwargs: Any) -> Any:
            return {"status": "ok"}

        def delete_collection(self, *args: Any, **kwargs: Any) -> Any:
            return True

    client = _Client()
    repo = VectorStoreRepository(_settings(), client=client)

    repo.close()
    assert client.closed == 1
    assert repo._client is None  # type: ignore[attr-defined]

    repo.close()
    assert client.closed == 1


def test_repository_loads_tenacity_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retry = object()
    retry_if_exception_type = object()
    stop_after_attempt = object()

    class _RetryError(Exception):
        pass

    def _wait_exponential(**_: Any) -> str:
        return "wait-exponential"

    tenacity_module = Mock()
    tenacity_module.retry = retry
    tenacity_module.retry_if_exception_type = retry_if_exception_type
    tenacity_module.stop_after_attempt = stop_after_attempt
    tenacity_module.RetryError = _RetryError

    wait_module = Mock()
    wait_module.wait_exponential.side_effect = lambda **kwargs: (
        "wait-exponential",
        kwargs,
    )

    def _fake_import(name: str) -> Mock:
        if name == "tenacity":
            return tenacity_module
        if name == "tenacity.wait":
            return wait_module
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("ragtrader_api.vectorstore.import_module", _fake_import)

    repo = VectorStoreRepository(_settings(), client=Mock())

    tenacity_support = repo._load_tenacity()
    assert tenacity_support is not None
    assert tenacity_support["retry"] is retry
    assert tenacity_support["retry_if_exception_type"] is retry_if_exception_type
    assert tenacity_support["stop_after_attempt"] is stop_after_attempt
    assert tenacity_support["RetryError"] is _RetryError
    assert tenacity_support["wait"][0] == "wait-exponential"

    # cached result should be returned on subsequent calls without re-import
    monkeypatch.setattr(
        "ragtrader_api.vectorstore.import_module", Mock(side_effect=AssertionError)
    )
    assert repo._load_tenacity() is tenacity_support


def test_repository_upsert_retries_transient_failures() -> None:
    class _FlakyClient(QdrantClientProtocol):
        def __init__(self) -> None:
            self.calls = 0

        def create_collection(self, *args: Any, **kwargs: Any) -> Any:
            return {"collection": kwargs.get("collection_name")}

        def upsert(self, *, collection_name: str, points: Any, **_: Any) -> str:
            self.calls += 1
            if self.calls < 3:
                raise ConnectionError("temporary failure")
            return f"{collection_name}:{len(list(points))}"

        def delete(self, *args: Any, **kwargs: Any) -> Any:
            return {"status": "noop"}

        def delete_collection(self, *args: Any, **kwargs: Any) -> Any:
            return True

    client = _FlakyClient()
    repo = VectorStoreRepository(
        _settings(),
        client=client,  # reuse injected instance
        retry_attempts=3,
        backoff_strategy=lambda _: 0.0,
    )

    result = repo.upsert_points("demo", points=deque([[1.0, 2.0, 3.0]]))

    assert result == "demo:1"
    assert client.calls == 3


def test_repository_raises_after_retry_budget_exhausted() -> None:
    class _FailingClient(QdrantClientProtocol):
        def create_collection(self, *args: Any, **kwargs: Any) -> Any:
            return {"collection": kwargs.get("collection_name")}

        def upsert(self, **_: Any) -> None:
            raise ConnectionError("still failing")

        def delete(self, *args: Any, **kwargs: Any) -> Any:
            return {"status": "noop"}

        def delete_collection(self, *args: Any, **kwargs: Any) -> Any:
            return True

    repo = VectorStoreRepository(
        _settings(),
        client=_FailingClient(),
        retry_attempts=2,
        backoff_strategy=lambda _: 0.0,
    )

    with pytest.raises(ConnectionError):
        repo.upsert_points("demo", points=[])


def test_repository_delete_points_delegates_to_client() -> None:
    client = Mock()
    client.delete.return_value = {"status": "ok"}

    repo = VectorStoreRepository(_settings(use_qdrant_cloud=False), client=client)
    selector = {"ids": [1, 2, 3]}

    assert repo.delete_points("demo", selector) == {"status": "ok"}
    client.delete.assert_called_once_with(
        collection_name="demo",
        points_selector=selector,
    )
