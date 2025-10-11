"""Utilities for parsing upstream content feeds into normalized records."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from html import unescape
from urllib.parse import SplitResult, urlsplit, urlunsplit

__all__ = [
    "ArticleCandidate",
    "BaseContentAdapter",
    "CoinDeskAdapter",
    "CoinTelegraphAdapter",
    "RedditAdapter",
    "UnsupportedLanguageError",
]


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


class UnsupportedLanguageError(ValueError):
    """Raised when a payload is not English-language content."""


class BaseContentAdapter:
    """Base class shared by the content adapters."""

    source_name: str
    canonical_host: str

    def parse(
        self, payload: Mapping[str, object]
    ) -> ArticleCandidate | None:  # pragma: no cover - interface only
        raise NotImplementedError

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
        elif isinstance(value, (int, float)):
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
            if isinstance(tickers, Iterable) and not isinstance(tickers, (str, bytes))
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
            if isinstance(tags, Iterable) and not isinstance(tags, (str, bytes))
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
            if isinstance(tickers, Iterable) and not isinstance(tickers, (str, bytes))
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
