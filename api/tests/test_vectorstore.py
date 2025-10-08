"""Contract tests for the Qdrant vector store repository."""

from __future__ import annotations

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
