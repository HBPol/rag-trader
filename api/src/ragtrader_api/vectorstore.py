"""Qdrant vector store repository abstraction."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Sequence
from importlib import import_module
from typing import Any

try:  # pragma: no cover - optional dependency guard
    from qdrant_client import QdrantClient
except ModuleNotFoundError:  # pragma: no cover - executed only when dependency missing

    class QdrantClient:  # type: ignore[override]
        """Fallback stub to provide a helpful error when qdrant-client is absent."""

        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # noqa: D401 - match Qdrant signature
            raise ModuleNotFoundError(
                "qdrant-client is required to use VectorStoreRepository."
                " Install the service dependencies via"
                " `pip install -e .[dev]`."
            )


from ragtrader_api.settings import ApiSettings

_LOGGER = logging.getLogger(__name__)


def _default_backoff(attempt: int) -> float:
    """Return an exponential backoff delay in seconds."""

    return min(0.1 * (2 ** (attempt - 1)), 1.0)


class VectorStoreRepository:
    """Repository wrapper that manages Qdrant client lifecycle and retries."""

    def __init__(
        self,
        settings: ApiSettings,
        *,
        client: QdrantClient | None = None,
        client_factory: Callable[..., QdrantClient] = QdrantClient,
        retry_attempts: int = 3,
        wait_strategy: Any | None = None,
        backoff_strategy: Callable[[int], float] | None = None,
        retryable_exceptions: tuple[type[BaseException], ...] | None = None,
    ) -> None:
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")

        self._settings = settings
        self._client_factory = client_factory
        self._client = client
        self._retry_attempts = retry_attempts
        self._wait_strategy = wait_strategy
        self._backoff_strategy = backoff_strategy or _default_backoff
        self._retryable_exceptions = retryable_exceptions or (
            ConnectionError,
            TimeoutError,
        )
        self._tenacity_support: dict[str, Any] | None = None

    @property
    def settings(self) -> ApiSettings:
        return self._settings

    def _build_client(self) -> QdrantClient:
        if self._client is None:
            factory_kwargs: dict[str, Any] = {"url": self._settings.qdrant_url}
            if self._settings.use_qdrant_cloud:
                if self._settings.qdrant_api_key:
                    factory_kwargs["api_key"] = self._settings.qdrant_api_key
                else:
                    _LOGGER.warning(
                        "Qdrant cloud mode enabled but no API key provided;"
                        " continuing without authentication."
                    )
            else:
                _LOGGER.debug(
                    "Initializing Qdrant self-hosted client for %s",
                    self._settings.qdrant_url,
                )

            self._client = self._client_factory(**factory_kwargs)
        return self._client

    def _load_tenacity(self) -> dict[str, Any] | None:
        if self._tenacity_support is None:
            try:
                tenacity = import_module("tenacity")
                wait_mod = import_module("tenacity.wait")
            except ModuleNotFoundError:
                self._tenacity_support = {}
            else:
                wait = self._wait_strategy or wait_mod.wait_exponential(
                    multiplier=0.1,
                    min=0.1,
                    max=1.0,
                )
                self._tenacity_support = {
                    "retry": tenacity.retry,
                    "retry_if_exception_type": tenacity.retry_if_exception_type,
                    "stop_after_attempt": tenacity.stop_after_attempt,
                    "RetryError": tenacity.RetryError,
                    "wait": wait,
                }
        return self._tenacity_support or None

    def _run_with_retry(self, operation: Callable[[QdrantClient], Any]) -> Any:
        tenacity = self._load_tenacity()
        if tenacity:

            @tenacity["retry"](
                reraise=True,
                stop=tenacity["stop_after_attempt"](self._retry_attempts),
                wait=tenacity["wait"],
                retry=tenacity["retry_if_exception_type"](self._retryable_exceptions),
            )
            def _runner() -> Any:
                return operation(self._build_client())

            try:
                return _runner()
            except tenacity["RetryError"] as exc:  # pragma: no cover - defensive path
                raise exc.last_attempt.exception() from exc

        attempt = 1
        while True:
            try:
                return operation(self._build_client())
            except self._retryable_exceptions as exc:
                if attempt >= self._retry_attempts:
                    raise

                delay = max(self._backoff_strategy(attempt), 0.0)
                _LOGGER.warning(
                    "Vector store operation failed (attempt %s/%s): %s",
                    attempt,
                    self._retry_attempts,
                    exc,
                )
                if delay:
                    time.sleep(delay)
                attempt += 1

    @property
    def client(self) -> QdrantClient:
        """Return the lazily-initialized Qdrant client."""

        return self._build_client()

    def create_collection(
        self,
        collection_name: str,
        vectors_config: Any,
        **kwargs: Any,
    ) -> Any:
        """Create a collection in Qdrant."""

        def _op(client: QdrantClient) -> Any:
            return client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config,
                **kwargs,
            )

        return self._run_with_retry(_op)

    def upsert_points(
        self,
        collection_name: str,
        points: Sequence[Any] | Iterable[Any],
        **kwargs: Any,
    ) -> Any:
        """Insert or update a batch of points."""

        def _op(client: QdrantClient) -> Any:
            return client.upsert(
                collection_name=collection_name,
                points=points,
                **kwargs,
            )

        return self._run_with_retry(_op)

    def delete_points(
        self,
        collection_name: str,
        points_selector: Any,
        **kwargs: Any,
    ) -> Any:
        """Delete selected points from a collection."""

        def _op(client: QdrantClient) -> Any:
            return client.delete(
                collection_name=collection_name,
                points_selector=points_selector,
                **kwargs,
            )

        return self._run_with_retry(_op)

    def delete_collection(self, collection_name: str, **kwargs: Any) -> Any:
        """Drop a collection entirely."""

        def _op(client: QdrantClient) -> Any:
            return client.delete_collection(collection_name=collection_name, **kwargs)

        return self._run_with_retry(_op)

    def close(self) -> None:
        """Close the underlying Qdrant client if supported."""

        if self._client is None:
            return

        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        self._client = None


__all__ = ["VectorStoreRepository"]
