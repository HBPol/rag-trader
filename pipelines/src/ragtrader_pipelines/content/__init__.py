"""Utilities for parsing upstream content feeds into normalized records."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from html import unescape
from importlib import import_module
from types import ModuleType
from typing import Any, Protocol, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx
from sqlalchemy import MetaData, Table, create_engine, delete, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..registry import PipelineRegistry
from ..sentiment import (
    SentimentAspect,
    SentimentClassifier,
    SentimentLabel,
    SentimentResult,
    SentimentSeriesPoint,
    ZScoreCalculator,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ArticleCandidate",
    "BaseContentAdapter",
    "ContentAggregator",
    "ContentIngestionJob",
    "CoinDeskAdapter",
    "CoinDeskContentSource",
    "CoinTelegraphAdapter",
    "CoinTelegraphContentSource",
    "InMemoryDedupeCache",
    "NormalizedArticleRecord",
    "RedditContentSource",
    "RedisDedupeCache",
    "build_arg_parser",
    "build_sources_from_env",
    "default_content_sources",
    "RedditAdapter",
    "SentimentRecord",
    "SqlAlchemyContentRepository",
    "SourceFactoryError",
    "SourceFetchError",
    "UnsupportedLanguageError",
    "main",
    "register_content_ingestion_job",
]


class ContentSource(Protocol):
    """Protocol describing the content source dependency."""

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Iterable[ArticleCandidate]:
        """Return candidate articles within the requested window."""


class SentimentClassifierProtocol(Protocol):
    """Protocol describing the sentiment classifier dependency."""

    def classify(
        self, text: str, metadata: Mapping[str, Any] | None
    ) -> SentimentResult:  # pragma: no cover - interface only
        ...


class ContentRepository(Protocol):
    """Protocol for the content repository dependency."""

    def upsert_article_with_sentiments(
        self,
        *,
        article: NormalizedArticleRecord,
        sentiments: Iterable[SentimentRecord],
    ) -> int:  # pragma: no cover - interface only
        ...


@dataclass(slots=True)
class ArticleCandidate:
    """Normalized representation of a candidate article."""

    source: str
    url: str
    title: str
    excerpt: str
    coins: list[str]
    published_ts: dt.datetime
    cache_key: str | None = None
    cache_expires_at: dt.datetime | None = None


@dataclass(slots=True)
class NormalizedArticleRecord:
    """Serializable record representing a normalized content article."""

    source: str
    url: str
    title: str
    excerpt: str
    coins: list[str] = field(default_factory=list)
    published_ts: dt.datetime | None = None


@dataclass(slots=True)
class SentimentRecord:
    """Serializable record for a sentiment analysis observation."""

    coin: str
    polarity: Decimal
    confidence: Decimal
    zscore_window: int
    aspects: list[str] = field(default_factory=list)
    ts: dt.datetime | None = None
    zscore: Decimal | None = None


class UnsupportedLanguageError(ValueError):
    """Raised when a payload is not English-language content."""


class BaseContentAdapter:
    """Base class shared by the content adapters."""

    source_name: str
    canonical_host: str

    def parse(self, payload: Mapping[str, object]) -> ArticleCandidate | None:
        raise NotImplementedError  # pragma: no cover - interface only

    # -- helpers -----------------------------------------------------------------
    @staticmethod
    def _normalize_url(url: str, *, canonical_host: str) -> str:
        """Normalise a URL for caching/deduplication purposes."""

        split = urlsplit(url, allow_fragments=True)
        netloc = canonical_host.lower()
        path = split.path or "/"
        path = re.sub(r"//+", "/", path)
        path = path.lower()

        normalized = SplitResult(
            scheme="https",
            netloc=netloc,
            path=path,
            query="",
            fragment="",
        )
        return urlunsplit(normalized)

    @staticmethod
    def _strip_html(value: str | None) -> str:
        if not value:
            return ""
        text = unescape(value)
        text = re.sub(r"<\s*br\s*/?>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return BaseContentAdapter._strip_html(value)

    @staticmethod
    def _parse_datetime(value: object) -> dt.datetime | None:
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            timestamp = value
        elif isinstance(value, int | float):
            timestamp = dt.datetime.fromtimestamp(float(value), tz=dt.UTC)
        elif isinstance(value, str) and value:
            try:
                timestamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Unable to parse datetime: {value}") from exc
        else:  # pragma: no cover - defensive
            raise TypeError(f"Unsupported datetime value: {value!r}")

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.UTC)
        return timestamp.astimezone(dt.UTC)

    @staticmethod
    def _normalize_coins(*collections: Iterable[str] | None) -> list[str]:
        if not collections:
            return []

        stopwords = {"NFT", "NFTS", "DEFI", "METAVERSE"}
        coins: set[str] = set()
        for collection in collections:
            if not collection:
                continue
            for token in collection:
                if not token:
                    continue
                normalized = re.sub(r"[^A-Za-z0-9]", "", str(token)).upper()
                if 2 <= len(normalized) <= 10 and normalized not in stopwords:
                    coins.add(normalized)
        return sorted(coins)

    @staticmethod
    def _is_english(payload: Mapping[str, object]) -> bool:
        language_keys = ("language", "language_hint", "lang")
        for key in language_keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                lowered = value.strip().lower()
                if lowered.startswith("en"):
                    return True
                if lowered in {"english", "eng"}:
                    return True
                return False
        return True


class CoinDeskAdapter(BaseContentAdapter):
    source_name = "coindesk"
    canonical_host = "www.coindesk.com"

    def parse(self, payload: Mapping[str, object]) -> ArticleCandidate | None:
        if not self._is_english(payload):
            raise UnsupportedLanguageError("CoinDesk payload not in English")

        def _first_value(*keys: str) -> object | None:
            for key in keys:
                value = payload.get(key)
                if value not in (None, ""):
                    return value
            return None

        url = _first_value("canonical_url", "url", "URL")
        title = _first_value("title", "headline", "TITLE")
        excerpt_value = _first_value("excerpt", "dek", "body", "EXCERPT", "DEK", "BODY")
        published = _first_value(
            "published_time",
            "publish_time",
            "published_at",
            "publish_date",
            "PUBLISHED_ON",
        )

        if not (
            isinstance(url, str)
            and url
            and isinstance(title, str)
            and title
            and published
        ):
            return None

        normalized_url = self._normalize_url(url, canonical_host=self.canonical_host)
        normalized_title = self._normalize_text(title)
        excerpt = self._normalize_text(
            excerpt_value if isinstance(excerpt_value, str) else ""
        )
        published_ts = self._parse_datetime(published)
        if not published_ts:
            return None

        def _string_tokens(value: object) -> list[str]:
            tokens: list[str] = []
            stack: list[object] = [value]
            while stack:
                current = stack.pop()
                if isinstance(current, str):
                    tokens.append(current)
                elif isinstance(current, Mapping):
                    stack.extend(current.values())
                elif isinstance(current, Iterable) and not isinstance(
                    current, (str | bytes)
                ):
                    stack.extend(list(current))
            return tokens

        tickers = payload.get("tickers")
        coins_field = payload.get("coins")
        uppercase_collections: list[list[str]] = []
        for key, value in payload.items():
            if not isinstance(key, str) or not key.isupper():
                continue
            if isinstance(value, Iterable) and not isinstance(value, (str | bytes)):
                tokens = _string_tokens(value)
                if tokens:
                    uppercase_collections.append(tokens)

        coins = self._normalize_coins(
            (
                tickers
                if isinstance(tickers, Iterable)
                and not isinstance(tickers, (str | bytes))
                else None
            ),
            (
                coins_field
                if isinstance(coins_field, Iterable)
                and not isinstance(coins_field, (str | bytes))
                else None
            ),
            *uppercase_collections,
        )

        cache_key = None
        identifier = _first_value("id", "slug", "guid", "GUID")
        if isinstance(identifier, str) and identifier:
            cache_key = identifier

        return ArticleCandidate(
            source=self.source_name,
            url=normalized_url,
            title=normalized_title,
            excerpt=excerpt,
            coins=coins,
            published_ts=published_ts,
            cache_key=cache_key or normalized_url,
        )


class CoinTelegraphAdapter(BaseContentAdapter):
    source_name = "cointelegraph"
    canonical_host = "cointelegraph.com"

    def parse(self, payload: Mapping[str, object]) -> ArticleCandidate | None:
        if not self._is_english(payload):
            raise UnsupportedLanguageError("CoinTelegraph payload not in English")

        url = payload.get("url")
        title = payload.get("headline")
        description = payload.get("description")
        published = payload.get("published_at")

        if not (
            isinstance(url, str)
            and url
            and isinstance(title, str)
            and title
            and published
        ):
            return None

        normalized_url = self._normalize_url(url, canonical_host=self.canonical_host)
        normalized_title = self._normalize_text(title)
        excerpt = self._normalize_text(
            description if isinstance(description, str) else ""
        )
        published_ts = self._parse_datetime(published)
        if not published_ts:
            return None

        tags = payload.get("tags")
        coins = self._normalize_coins(
            tags
            if isinstance(tags, Iterable) and not isinstance(tags, str | bytes)
            else None
        )

        cache_key = None
        identifier = payload.get("id")
        if isinstance(identifier, str) and identifier:
            cache_key = identifier

        return ArticleCandidate(
            source=self.source_name,
            url=normalized_url,
            title=normalized_title,
            excerpt=excerpt,
            coins=coins,
            published_ts=published_ts,
            cache_key=cache_key or normalized_url,
        )


class RedditAdapter(BaseContentAdapter):
    source_name = "reddit"
    canonical_host = "www.reddit.com"

    def parse(self, payload: Mapping[str, object]) -> ArticleCandidate | None:
        if not self._is_english(payload):
            raise UnsupportedLanguageError("Reddit payload not in English")

        url = payload.get("url")
        title = payload.get("title")
        body = payload.get("selftext")
        created = payload.get("created_utc")

        if not (
            isinstance(url, str)
            and url
            and isinstance(title, str)
            and title
            and created is not None
        ):
            return None

        normalized_url = self._normalize_url(url, canonical_host=self.canonical_host)
        normalized_title = self._normalize_text(title)
        excerpt = self._normalize_text(body if isinstance(body, str) else "")
        published_ts = self._parse_datetime(created)
        if not published_ts:
            return None

        tickers = payload.get("tickers")
        coins = self._normalize_coins(
            tickers
            if isinstance(tickers, Iterable) and not isinstance(tickers, str | bytes)
            else None
        )

        cache_key = None
        identifier = payload.get("id")
        if isinstance(identifier, str) and identifier:
            cache_key = identifier

        return ArticleCandidate(
            source=self.source_name,
            url=normalized_url,
            title=normalized_title,
            excerpt=excerpt,
            coins=coins,
            published_ts=published_ts,
            cache_key=cache_key or normalized_url,
        )


class RedisClient(Protocol):
    """Subset of the Redis client interface used for deduplication."""

    def get(self, key: str) -> Any:  # pragma: no cover - interface only
        ...

    def setex(
        self, key: str, time: int, value: str
    ) -> Any:  # pragma: no cover - interface only
        ...


class DedupeCache(Protocol):
    """Protocol describing the persistence for deduplication state."""

    def get(self, key: str) -> dt.datetime | None:  # pragma: no cover - interface only
        ...

    def set(
        self, key: str, expiry: dt.datetime, now: dt.datetime
    ) -> None:  # pragma: no cover - interface only
        ...

    def prune(self, now: dt.datetime) -> None:  # pragma: no cover - interface only
        ...


class InMemoryDedupeCache:
    """In-memory implementation of :class:`DedupeCache`."""

    def __init__(self) -> None:
        self._entries: dict[str, dt.datetime] = {}

    def get(self, key: str) -> dt.datetime | None:
        return self._entries.get(key)

    def set(self, key: str, expiry: dt.datetime, now: dt.datetime) -> None:
        _ = now
        self._entries[key] = expiry

    def prune(self, now: dt.datetime) -> None:
        expired = [key for key, expiry in self._entries.items() if expiry <= now]
        for key in expired:
            self._entries.pop(key, None)


class RedisDedupeCache:
    """Redis-backed implementation of :class:`DedupeCache`."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    def get(self, key: str) -> dt.datetime | None:
        value = self._client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        try:
            timestamp = dt.datetime.fromisoformat(value)
        except ValueError:  # pragma: no cover - defensive
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.UTC)
        return timestamp

    def set(self, key: str, expiry: dt.datetime, now: dt.datetime) -> None:
        ttl = int(max((expiry - now).total_seconds(), 1))
        self._client.setex(key, ttl, expiry.isoformat())

    def prune(self, now: dt.datetime) -> None:
        _ = now


class ContentAggregator:
    """Deduplicate :class:`ArticleCandidate` objects across sources."""

    def __init__(
        self,
        *,
        freshness_window: dt.timedelta,
        clock: Callable[[], dt.datetime] | None = None,
        cache: DedupeCache | None = None,
    ) -> None:
        self._freshness_window = freshness_window
        self._clock = clock or (lambda: dt.datetime.now(tz=dt.UTC))
        self._cache = cache or InMemoryDedupeCache()

    def emit(
        self, source: str, candidates: Iterable[ArticleCandidate]
    ) -> Iterator[ArticleCandidate]:
        """Yield deduplicated candidates for the given source."""

        _ = source  # placeholder for future per-source policies

        now = self._clock()
        self._cache.prune(now)

        for candidate in candidates:
            normalized_url = self._normalise_candidate_url(candidate)
            normalized_title = candidate.title.strip().lower()
            cache_key = f"{normalized_url}::{normalized_title}"

            now = self._clock()
            expiry = self._cache.get(cache_key)
            if expiry and expiry >= now:
                continue

            expiry = now + self._freshness_window
            self._cache.set(cache_key, expiry, now)

            if not candidate.cache_key:
                candidate.cache_key = cache_key
            candidate.cache_expires_at = expiry

            yield candidate

        self._cache.prune(self._clock())

    def _normalise_candidate_url(self, candidate: ArticleCandidate) -> str:
        parsed = urlsplit(candidate.url)
        canonical_host = parsed.netloc.lower()
        if not canonical_host:
            return candidate.url
        return BaseContentAdapter._normalize_url(
            candidate.url,
            canonical_host=canonical_host,
        )


_CONTENT_SOURCE_EXPORTS = (
    "CoinDeskContentSource",
    "CoinTelegraphContentSource",
    "RedditContentSource",
    "SourceFactoryError",
    "SourceFetchError",
    "build_sources_from_env",
)

_content_sources_module: ModuleType | None = None


def _load_content_sources() -> ModuleType:
    """Import the content sources module on demand and cache the result."""

    global _content_sources_module
    if _content_sources_module is None:
        module = import_module(".sources", __name__)
        globals().update(
            {name: getattr(module, name) for name in _CONTENT_SOURCE_EXPORTS}
        )
        _content_sources_module = module
    return _content_sources_module


def __getattr__(name: str) -> Any:
    if name in _CONTENT_SOURCE_EXPORTS:
        module = _load_content_sources()
        return getattr(module, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CONTENT_SOURCE_EXPORTS))


_DEFAULT_ADAPTER_SLUGS: tuple[str, ...] = (
    "coindesk",
    "cointelegraph",
    "reddit",
)


def _normalize_adapter_slugs(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        slug = value.strip().lower()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        normalized.append(slug)
    return normalized


def default_content_sources(
    adapters: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    coindesk_client: httpx.Client | None = None,
    cointelegraph_client: httpx.Client | None = None,
    reddit_token_client: httpx.Client | None = None,
    reddit_api_client: httpx.Client | None = None,
    reddit_subreddits: Sequence[str] | None = None,
    clock: Callable[[], dt.datetime] | None = None,
) -> Mapping[str, ContentSource]:
    """Instantiate content sources from environment configuration."""

    sources_module = _load_content_sources()
    selected = _normalize_adapter_slugs(adapters or _DEFAULT_ADAPTER_SLUGS)
    factories = sources_module.build_sources_from_env(
        env=env,
        coindesk_client=coindesk_client,
        cointelegraph_client=cointelegraph_client,
        reddit_token_client=reddit_token_client,
        reddit_api_client=reddit_api_client,
        reddit_subreddits=reddit_subreddits,
        clock=clock,
    )

    sources: dict[str, ContentSource] = {}
    for slug in selected:
        factory = factories.get(slug)
        if factory is None:
            msg = f"Unknown content adapter '{slug}'"
            raise sources_module.SourceFactoryError(msg)
        try:
            source = factory()
        except sources_module.SourceFactoryError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            msg = f"Failed to instantiate adapter '{slug}'"
            raise sources_module.SourceFactoryError(msg) from exc
        sources[slug] = source
    return sources


def _parse_adapter_argument(
    value: str | Sequence[str] | None,
) -> list[str]:
    if value is None:
        return list(_DEFAULT_ADAPTER_SLUGS)
    if isinstance(value, str):
        tokens = value.split(",")
    else:
        tokens = list(value)
    return _normalize_adapter_slugs(tokens)


def _maybe_build_dedupe_cache(url: str | None) -> DedupeCache | None:
    if not url:
        return None
    try:
        redis_mod = import_module("redis")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dep
        msg = "redis package is required when CONTENT_DEDUPE_URL is set"
        raise RuntimeError(msg) from exc

    client = cast(RedisClient, redis_mod.Redis.from_url(url, decode_responses=True))
    return RedisDedupeCache(client)


class ContentIngestionJob:
    """Coordinate content ingestion, classification, and persistence."""

    def __init__(
        self,
        *,
        sources: Mapping[str, ContentSource],
        aggregator: ContentAggregator,
        classifier: SentimentClassifierProtocol,
        repository: ContentRepository,
        zscore_calculator: ZScoreCalculator,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._sources = dict(sources)
        self._aggregator = aggregator
        self._classifier = classifier
        self._repository = repository
        self._zscore_calculator = zscore_calculator
        self._clock = clock or (lambda: dt.datetime.now(tz=dt.UTC))

    def run(self, *, lookback: dt.timedelta) -> None:
        if lookback <= dt.timedelta(0):  # pragma: no cover - sanity check
            msg = "lookback must be greater than zero"
            raise ValueError(msg)

        end = self._ensure_aware(self._clock())
        start = end - lookback

        candidates: list[ArticleCandidate] = []
        sources_module = _load_content_sources()
        source_fetch_error_cls = sources_module.SourceFetchError
        for name, source in self._sources.items():
            try:
                batch = list(source.fetch(start, end))
            except source_fetch_error_cls as exc:
                slug = getattr(exc, "slug", name)
                detail = getattr(exc, "original_exc", exc)
                logger.warning(
                    "Skipping content source '%s' due to fetch failure: %s",
                    slug,
                    detail,
                )
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "Skipping content source '%s' due to HTTP error: %s",
                    name,
                    exc,
                )
                continue
            deduped = list(self._aggregator.emit(name, batch))
            candidates.extend(deduped)

        candidates.sort(key=self._candidate_sort_key)

        article_payloads: list[
            tuple[NormalizedArticleRecord, list[SentimentRecord]]
        ] = []
        zscore_points: list[SentimentSeriesPoint] = []
        zscore_index: dict[tuple[str, int], list[SentimentRecord]] = {}

        for candidate in candidates:
            article = NormalizedArticleRecord(
                source=candidate.source,
                url=candidate.url,
                title=candidate.title,
                excerpt=candidate.excerpt,
                coins=list(candidate.coins),
                published_ts=candidate.published_ts,
            )

            text = self._compose_text(candidate)
            metadata = {"coins": list(candidate.coins)}
            result = self._classifier.classify(text, metadata)

            sentiments: list[SentimentRecord] = []
            polarity = self._polarity_for_label(result.label)
            confidence = Decimal(str(result.confidence))
            aspects = self._normalize_aspects(result.aspects)

            for coin in result.coins:
                record = SentimentRecord(
                    coin=str(coin),
                    polarity=polarity,
                    confidence=confidence,
                    zscore_window=self._zscore_calculator.window,
                    aspects=list(aspects),
                    ts=candidate.published_ts,
                )
                sentiments.append(record)

                timestamp = int(candidate.published_ts.timestamp())
                point = SentimentSeriesPoint(
                    coin=str(coin),
                    timestamp=timestamp,
                    score=float(record.polarity),
                )
                zscore_points.append(point)
                index_key = (point.coin, point.timestamp)
                zscore_index.setdefault(index_key, []).append(record)

            article_payloads.append((article, sentiments))

        if zscore_points:
            for zscore in self._zscore_calculator.calculate(zscore_points):
                key = (zscore.coin, zscore.timestamp)
                records = zscore_index.get(key)
                if not records:
                    continue
                record = records.pop(0)
                record.zscore = Decimal(str(zscore.z_score))

        for article, sentiments in article_payloads:
            self._repository.upsert_article_with_sentiments(
                article=article, sentiments=sentiments
            )

    @staticmethod
    def _compose_text(candidate: ArticleCandidate) -> str:
        parts = [candidate.title.strip()]
        excerpt = candidate.excerpt.strip()
        if excerpt:
            parts.append(excerpt)
        return "\n\n".join(parts)

    @staticmethod
    def _candidate_sort_key(
        candidate: ArticleCandidate,
    ) -> tuple[dt.datetime, str, str, str]:
        return (
            candidate.published_ts,
            candidate.source,
            candidate.url,
            candidate.title,
        )

    @staticmethod
    def _ensure_aware(value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)

    @staticmethod
    def _normalize_aspects(values: Sequence[SentimentAspect | str]) -> list[str]:
        normalized: list[str] = []
        for aspect in values:
            if isinstance(aspect, SentimentAspect):
                normalized.append(aspect.value.lower())
            else:
                normalized.append(str(aspect).lower())
        return normalized

    @staticmethod
    def _polarity_for_label(label: SentimentLabel) -> Decimal:
        mapping = {
            SentimentLabel.BULLISH: Decimal("1"),
            SentimentLabel.BEARISH: Decimal("-1"),
        }
        return mapping.get(label, Decimal("0"))


class SqlAlchemyContentRepository:
    """Persist normalized content and related sentiments using SQLAlchemy."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        metadata = MetaData()
        self._articles = Table("articles", metadata, autoload_with=engine)
        self._sentiments = Table("sentiments", metadata, autoload_with=engine)

    def upsert_article_with_sentiments(
        self,
        *,
        article: NormalizedArticleRecord,
        sentiments: Iterable[SentimentRecord],
    ) -> int:
        """Persist an article and associated sentiments, returning the article id."""

        sentiment_records = list(sentiments)

        with Session(self._engine) as session:
            try:
                article_id = self._upsert_article(session, article)
                if sentiment_records:
                    self._replace_sentiments(session, article_id, sentiment_records)
                session.commit()
            except Exception:  # pragma: no cover - defensive cleanup
                session.rollback()
                raise

        return article_id

    def _upsert_article(
        self, session: Session, article: NormalizedArticleRecord
    ) -> int:
        values = {
            "source": article.source,
            "url": article.url,
            "title": article.title,
            "body_excerpt": article.excerpt,
            "coins": list(article.coins),
            "published_ts": article.published_ts,
        }

        stmt = (
            pg_insert(self._articles)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[self._articles.c.url],
                set_=values,
            )
            .returning(self._articles.c.id)
        )

        result = session.execute(stmt)
        return cast(int, result.scalar_one())

    def _replace_sentiments(
        self,
        session: Session,
        article_id: int,
        sentiments: list[SentimentRecord],
    ) -> None:
        combos = {(record.coin, record.zscore_window) for record in sentiments}
        if combos:
            delete_stmt = (
                delete(self._sentiments)
                .where(self._sentiments.c.article_id == article_id)
                .where(
                    tuple_(
                        self._sentiments.c.coin, self._sentiments.c.zscore_window
                    ).in_(list(combos))
                )
            )
            session.execute(delete_stmt)

        insert_payload = [
            {
                "article_id": article_id,
                "coin": record.coin,
                "polarity": record.polarity,
                "aspects": list(record.aspects),
                "confidence": record.confidence,
                "ts": record.ts,
                "zscore_window": record.zscore_window,
                "zscore": record.zscore,
            }
            for record in sentiments
        ]

        if insert_payload:
            session.execute(self._sentiments.insert(), insert_payload)


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct an argument parser for the content ingestion CLI."""

    parser = argparse.ArgumentParser(
        description="Run the content ingestion pipeline and persist results"
    )
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        default=240,
        help="Number of minutes to look back when fetching content",
    )
    parser.add_argument(
        "--freshness-minutes",
        type=int,
        default=15,
        help="Deduplication freshness window in minutes",
    )
    parser.add_argument(
        "--zscore-window",
        type=int,
        default=6,
        help="Number of observations for the rolling z-score window",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Database DSN for persisting content and sentiments",
    )
    parser.add_argument(
        "--adapters",
        default=",".join(_DEFAULT_ADAPTER_SLUGS),
        help=(
            "Comma-separated list of content adapters to enable. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--source-factory",
        help=(
            "Dotted path to a callable returning a mapping of source name to "
            "content source instances (overrides --adapters)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI wiring
    args = build_arg_parser().parse_args(argv)

    lookback = dt.timedelta(minutes=args.lookback_minutes)
    freshness = dt.timedelta(minutes=args.freshness_minutes)
    zscore_window = int(args.zscore_window)

    database_url = args.database_url or os.environ.get("DATABASE_URL", "")
    if not database_url:
        msg = "DATABASE_URL must be provided to persist content"
        raise SystemExit(msg)

    adapter_slugs = _parse_adapter_argument(args.adapters)

    if args.source_factory:
        factory = _load_factory(args.source_factory)
        sources = factory()
        if not isinstance(sources, Mapping):
            msg = "Source factory must return a mapping of sources"
            raise SystemExit(msg)
        sources = dict(sources)
    else:
        sources_module = _load_content_sources()
        try:
            sources = dict(
                default_content_sources(
                    adapters=adapter_slugs,
                    env=os.environ,
                    clock=lambda: dt.datetime.now(tz=dt.UTC),
                )
            )
        except sources_module.SourceFactoryError as exc:
            raise SystemExit(str(exc)) from exc

    engine = create_engine(database_url, future=True)
    repository = SqlAlchemyContentRepository(engine)
    try:
        dedupe_cache = _maybe_build_dedupe_cache(os.environ.get("CONTENT_DEDUPE_URL"))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    aggregator = ContentAggregator(
        freshness_window=freshness,
        clock=lambda: dt.datetime.now(tz=dt.UTC),
        cache=dedupe_cache,
    )
    classifier = SentimentClassifier()
    zscore_calculator = ZScoreCalculator(window=zscore_window)
    job = ContentIngestionJob(
        sources=sources,
        aggregator=aggregator,
        classifier=classifier,
        repository=repository,
        zscore_calculator=zscore_calculator,
        clock=lambda: dt.datetime.now(tz=dt.UTC),
    )
    job.run(lookback=lookback)
    return 0


def register_content_ingestion_job(
    registry: PipelineRegistry,
    *,
    database_url: str,
    lookback: dt.timedelta,
    freshness: dt.timedelta,
    source_factory: Callable[[], Mapping[str, ContentSource]],
    zscore_window: int = 6,
    dedupe_cache: DedupeCache | None = None,
) -> None:
    """Register the content ingestion job with the provided registry."""

    engine = create_engine(database_url, future=True)
    repository = SqlAlchemyContentRepository(engine)

    configured_cache = dedupe_cache
    if configured_cache is None:
        dedupe_url = os.environ.get("CONTENT_DEDUPE_URL")
        if dedupe_url:
            configured_cache = _maybe_build_dedupe_cache(dedupe_url)

    def _pipeline() -> None:
        sources = dict(source_factory())

        def _clock() -> dt.datetime:
            return dt.datetime.now(tz=dt.UTC)

        aggregator = ContentAggregator(
            freshness_window=freshness,
            clock=_clock,
            cache=configured_cache,
        )
        classifier = SentimentClassifier()
        zscore_calculator = ZScoreCalculator(window=zscore_window)
        job = ContentIngestionJob(
            sources=sources,
            aggregator=aggregator,
            classifier=classifier,
            repository=repository,
            zscore_calculator=zscore_calculator,
            clock=_clock,
        )
        job.run(lookback=lookback)

    registry.register("content.ingestion", _pipeline)


def _load_factory(path: str) -> Callable[[], Mapping[str, ContentSource]]:
    """Load a factory callable from a dotted path string."""

    module_name: str
    attr_name: str
    if ":" in path:
        module_name, attr_name = path.split(":", 1)
    else:
        module_name, attr_name = path.rsplit(".", 1)
    module = import_module(module_name)
    factory = getattr(module, attr_name)
    if not callable(factory):  # pragma: no cover - defensive branch
        msg = f"Factory '{path}' is not callable"
        raise TypeError(msg)
    return cast(Callable[[], Mapping[str, ContentSource]], factory)


if __name__ == "__main__":  # pragma: no cover - module CLI entrypoint
    raise SystemExit(main())
