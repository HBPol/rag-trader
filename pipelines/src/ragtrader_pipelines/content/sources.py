"""Concrete :class:`ContentSource` implementations for upstream providers."""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import httpx

from . import (
    ArticleCandidate,
    BaseContentAdapter,
    CoinDeskAdapter,
    CoinTelegraphAdapter,
    ContentSource,
    RedditAdapter,
    UnsupportedLanguageError,
)

__all__ = [
    "CoinDeskContentSource",
    "CoinTelegraphContentSource",
    "RedditContentSource",
    "SourceFactoryError",
    "SourceFetchError",
    "build_sources_from_env",
]

_DEFAULT_REDDIT_SUBREDDITS = ("cryptocurrency", "bitcoin", "ethereum")
_COINDESK_DEFAULT_BASE_URL = "https://data-api.coindesk.com"


class SourceFactoryError(RuntimeError):
    """Raised when a content source cannot be instantiated from the environment."""


class SourceFetchError(RuntimeError):
    """Raised when a content source fails to fetch upstream content."""

    def __init__(self, *, slug: str, exc: Exception) -> None:
        message = f"Failed to fetch content from source '{slug}'"
        super().__init__(message)
        self.slug = slug
        self.original_exc = exc


def _normalize_payload_items(payload: Any) -> list[Mapping[str, object]]:
    """Best-effort normalization of nested payload shapes into mappings."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]

    if isinstance(payload, Mapping):
        # Common keys exposed by the upstream feeds we integrate with.
        for key in ("items", "results", "data", "articles", "stories"):
            value = payload.get(key)
            items = _normalize_payload_items(value)
            if items:
                return items
        if isinstance(payload.get("children"), list):
            return [
                child.get("data", {})
                for child in payload["children"]
                if isinstance(child, Mapping)
            ]
    return []


class _BaseHttpSource(ContentSource):
    """Shared functionality for JSON-based HTTP content sources."""

    def __init__(
        self,
        *,
        adapter: BaseContentAdapter,
        client: httpx.Client,
        endpoint: str,
        limit: int,
    ) -> None:
        self._adapter = adapter
        self._client = client
        self._endpoint = endpoint
        self._limit = limit
        self._slug = getattr(adapter, "source_name", adapter.__class__.__name__.lower())

    def _filter_window(
        self,
        candidates: Iterable[ArticleCandidate],
        *,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Iterable[ArticleCandidate]:
        for candidate in candidates:
            published = candidate.published_ts
            if published and start <= published <= end:
                yield candidate

    def _parse_items(self, payload: Any) -> Iterable[ArticleCandidate]:
        items = _normalize_payload_items(payload)
        for item in items:
            if not isinstance(item, Mapping):
                continue
            try:
                candidate = self._adapter.parse(item)
            except UnsupportedLanguageError:
                continue
            if candidate:
                yield candidate


class CoinDeskContentSource(_BaseHttpSource):
    """Fetch latest CoinDesk articles via the CoinDesk Data API."""

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        adapter: CoinDeskAdapter | None = None,
        base_url: str = _COINDESK_DEFAULT_BASE_URL,
        endpoint: str = "/news/v1/article/list",
        limit: int = 100,
    ) -> None:
        if not api_key:
            msg = (
                "CONTENT_COINDESK_API_KEY (or CONTENT_RSS_COINDESK_API_KEY) "
                "must be configured"
            )
            raise SourceFactoryError(msg)

        client = client or httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        super().__init__(
            adapter=adapter or CoinDeskAdapter(),
            client=client,
            endpoint=endpoint,
            limit=limit,
        )
        self._headers = {
            "accept": "application/json",
            "x-api-key": api_key,
        }

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Iterable[ArticleCandidate]:
        params: dict[str, str] = {
            "published_time_start": start.astimezone(dt.UTC).isoformat(),
            "published_time_end": end.astimezone(dt.UTC).isoformat(),
            "limit": str(self._limit),
        }
        try:
            response = self._client.get(
                self._endpoint,
                params=params,
                headers=self._headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceFetchError(slug=self._slug, exc=exc) from exc
        payload = response.json()
        candidates = self._parse_items(payload)
        return list(self._filter_window(candidates, start=start, end=end))


class CoinTelegraphContentSource(_BaseHttpSource):
    """Fetch CoinTelegraph articles using their public JSON feed."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        adapter: CoinTelegraphAdapter | None = None,
        endpoint: str = "/api/v1/content/articles",
        limit: int = 100,
    ) -> None:
        client = client or httpx.Client(
            base_url="https://cointelegraph.com",
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        super().__init__(
            adapter=adapter or CoinTelegraphAdapter(),
            client=client,
            endpoint=endpoint,
            limit=limit,
        )

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Iterable[ArticleCandidate]:
        params: dict[str, str] = {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "limit": str(self._limit),
        }
        try:
            response = self._client.get(self._endpoint, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceFetchError(slug=self._slug, exc=exc) from exc
        payload = response.json()
        candidates = self._parse_items(payload)
        return list(self._filter_window(candidates, start=start, end=end))


class RedditContentSource(ContentSource):
    """Fetch Reddit submissions via the OAuth API."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_client: httpx.Client | None = None,
        api_client: httpx.Client | None = None,
        adapter: RedditAdapter | None = None,
        subreddits: Sequence[str] | None = None,
        limit: int = 100,
        clock: Callable[[], dt.datetime] | None = None,
        user_agent: str = "ragtrader-pipelines/0.1",
    ) -> None:
        if not client_id or not client_secret:
            msg = (
                "CONTENT_REDDIT_CLIENT_ID and CONTENT_REDDIT_CLIENT_SECRET must be "
                "configured"
            )
            raise SourceFactoryError(msg)

        self._client_id = client_id
        self._client_secret = client_secret
        self._token_client = token_client or httpx.Client(
            base_url="https://www.reddit.com",
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": user_agent},
        )
        self._api_client = api_client or httpx.Client(
            base_url="https://oauth.reddit.com",
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": user_agent},
        )
        self._adapter = adapter or RedditAdapter()
        self._slug = getattr(self._adapter, "source_name", "reddit")
        self._subreddits = tuple(subreddits or _DEFAULT_REDDIT_SUBREDDITS)
        self._limit = limit
        self._clock = clock or (lambda: dt.datetime.now(tz=dt.UTC))
        self._token: str | None = None
        self._token_expiry: dt.datetime | None = None

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Iterable[ArticleCandidate]:
        token = self._ensure_token()
        headers = {"Authorization": f"bearer {token}"}
        window: list[ArticleCandidate] = []

        for subreddit in self._subreddits:
            path = f"/r/{subreddit}/new"
            params = {"limit": self._limit}
            try:
                response = self._api_client.get(path, params=params, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SourceFetchError(slug=self._slug, exc=exc) from exc
            payload = response.json()
            items = _normalize_payload_items(payload)
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                try:
                    candidate = self._adapter.parse(item)
                except UnsupportedLanguageError:
                    continue
                if candidate and candidate.published_ts:
                    if start <= candidate.published_ts <= end:
                        window.append(candidate)
        return window

    def _ensure_token(self) -> str:
        now = self._clock()
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        try:
            response = self._token_client.post(
                "/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceFetchError(slug=self._slug, exc=exc) from exc
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            msg = "Reddit token response missing 'access_token'"
            raise SourceFactoryError(msg)
        expires_in = payload.get("expires_in", 3600)
        try:
            ttl = int(expires_in)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            ttl = 3600
        self._token = token
        self._token_expiry = now + dt.timedelta(seconds=max(ttl - 60, 60))
        return token


def build_sources_from_env(
    *,
    env: Mapping[str, str] | None = None,
    coindesk_client: httpx.Client | None = None,
    cointelegraph_client: httpx.Client | None = None,
    reddit_token_client: httpx.Client | None = None,
    reddit_api_client: httpx.Client | None = None,
    reddit_subreddits: Sequence[str] | None = None,
    clock: Callable[[], dt.datetime] | None = None,
) -> Mapping[str, Callable[[], ContentSource]]:
    """Return callables that build the default content sources."""

    env_map = dict(os.environ if env is None else env)

    def _coindesk_factory() -> ContentSource:
        api_key = (
            env_map.get("CONTENT_COINDESK_API_KEY")
            or env_map.get("CONTENT_RSS_COINDESK_API_KEY")
            or ""
        ).strip()
        base_url = (
            env_map.get("CONTENT_COINDESK_BASE_URL", "").strip()
            or env_map.get("CONTENT_RSS_COINDESK_BASE_URL", "").strip()
        )
        kwargs: dict[str, Any] = {"api_key": api_key}
        if coindesk_client is not None:
            kwargs["client"] = coindesk_client
        if base_url:
            kwargs["base_url"] = base_url
        return CoinDeskContentSource(**kwargs)

    def _cointelegraph_factory() -> ContentSource:
        return CoinTelegraphContentSource(client=cointelegraph_client)

    def _reddit_factory() -> ContentSource:
        client_id = env_map.get("CONTENT_REDDIT_CLIENT_ID", "")
        client_secret = env_map.get("CONTENT_REDDIT_CLIENT_SECRET", "")
        return RedditContentSource(
            client_id=client_id,
            client_secret=client_secret,
            token_client=reddit_token_client,
            api_client=reddit_api_client,
            subreddits=reddit_subreddits,
            clock=clock,
        )

    return {
        "coindesk": _coindesk_factory,
        "cointelegraph": _cointelegraph_factory,
        "reddit": _reddit_factory,
    }
