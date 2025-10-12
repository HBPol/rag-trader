"""Utilities for parsing upstream content feeds into normalized records."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from html import unescape
from importlib import import_module
from typing import Any, Protocol, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

from sqlalchemy import MetaData, Table, create_engine, delete, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

__all__ = [
    "ArticleCandidate",
    "BaseContentAdapter",
    "ContentAggregator",
    "ContentIngestionJob",
    "CoinDeskAdapter",
    "CoinTelegraphAdapter",
    "NormalizedArticleRecord",
    "build_arg_parser",
    "RedditAdapter",
    "SentimentRecord",
    "SqlAlchemyContentRepository",
    "UnsupportedLanguageError",
    "main",
    "register_content_ingestion_job",
]

from .registry import PipelineRegistry
from .sentiment import (
    SentimentAspect,
    SentimentClassifier,
    SentimentLabel,
    SentimentResult,
    SentimentSeriesPoint,
    ZScoreCalculator,
)


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

        url = payload.get("link")
        title = payload.get("title")
        summary = payload.get("summary")
        published = payload.get("published")

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
        excerpt = self._normalize_text(summary if isinstance(summary, str) else "")
        published_ts = self._parse_datetime(published)
        if not published_ts:
            return None

        tickers = payload.get("tickers")
        coins = self._normalize_coins(
            tickers
            if isinstance(tickers, Iterable) and not isinstance(tickers, str | bytes)
            else None
        )

        cache_key = None
        guid = payload.get("guid")
        if isinstance(guid, str) and guid:
            cache_key = guid

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


class ContentAggregator:
    """Deduplicate :class:`ArticleCandidate` objects across sources."""

    def __init__(
        self,
        *,
        freshness_window: dt.timedelta,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._freshness_window = freshness_window
        self._clock = clock or (lambda: dt.datetime.now(tz=dt.UTC))
        self._cache: dict[str, dt.datetime] = {}

    def emit(
        self, source: str, candidates: Iterable[ArticleCandidate]
    ) -> Iterator[ArticleCandidate]:
        """Yield deduplicated candidates for the given source."""

        _ = source  # placeholder for future per-source policies

        now = self._clock()
        self._prune(now)

        for candidate in candidates:
            normalized_url = self._normalise_candidate_url(candidate)
            normalized_title = candidate.title.strip().lower()
            cache_key = f"{normalized_url}::{normalized_title}"

            now = self._clock()
            expiry = self._cache.get(cache_key)
            if expiry and expiry >= now:
                continue

            expiry = now + self._freshness_window
            self._cache[cache_key] = expiry

            if not candidate.cache_key:
                candidate.cache_key = cache_key
            candidate.cache_expires_at = expiry

            yield candidate

        self._prune(self._clock())

    def _prune(self, now: dt.datetime) -> None:
        if not self._cache:
            return
        expired = [key for key, expiry in self._cache.items() if expiry <= now]
        for key in expired:
            self._cache.pop(key, None)

    def _normalise_candidate_url(self, candidate: ArticleCandidate) -> str:
        parsed = urlsplit(candidate.url)
        canonical_host = parsed.netloc.lower()
        if not canonical_host:
            return candidate.url
        return BaseContentAdapter._normalize_url(
            candidate.url,
            canonical_host=canonical_host,
        )


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
        for name, source in self._sources.items():
            batch = list(source.fetch(start, end))
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
        "--source-factory",
        required=True,
        help=(
            "Dotted path to a callable returning a mapping of source name to "
            "content source instances"
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

    factory = _load_factory(args.source_factory)
    sources = factory()
    if not isinstance(sources, Mapping):
        msg = "Source factory must return a mapping of sources"
        raise SystemExit(msg)
    sources = dict(sources)

    engine = create_engine(database_url, future=True)
    repository = SqlAlchemyContentRepository(engine)
    aggregator = ContentAggregator(
        freshness_window=freshness, clock=lambda: dt.datetime.now(tz=dt.UTC)
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
) -> None:
    """Register the content ingestion job with the provided registry."""

    engine = create_engine(database_url, future=True)
    repository = SqlAlchemyContentRepository(engine)

    def _pipeline() -> None:
        sources = dict(source_factory())

        def _clock() -> dt.datetime:
            return dt.datetime.now(tz=dt.UTC)

        aggregator = ContentAggregator(freshness_window=freshness, clock=_clock)
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
