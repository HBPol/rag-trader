"""Sentiment query services for the API layer."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db import database
from .db.models import Article, Sentiment
from .settings import ApiSettings


def _to_float(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_symbol(symbol: str) -> str:
    candidate = symbol.strip().upper()
    if not candidate:
        raise ValueError("symbol must be a non-empty string")
    if "-" in candidate:
        return candidate.split("-", 1)[0]
    return candidate


_WINDOW_UNIT_MULTIPLIERS: dict[str, int] = {
    "": 1,
    "m": 1,
    "min": 1,
    "mins": 1,
    "minute": 1,
    "minutes": 1,
    "h": 60,
    "hr": 60,
    "hrs": 60,
    "hour": 60,
    "hours": 60,
    "d": 60 * 24,
    "day": 60 * 24,
    "days": 60 * 24,
}

_WINDOW_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[a-z]*)$")


def _coerce_window(window: str) -> int:
    candidate = window.strip().lower()
    if not candidate:
        raise ValueError("window must be provided")

    match = _WINDOW_PATTERN.match(candidate)
    if not match:
        raise ValueError("window must be an integer optionally followed by units")

    value = int(match.group("value"))
    unit = match.group("unit")
    if unit not in _WINDOW_UNIT_MULTIPLIERS:
        raise ValueError("Unsupported window units for sentiment query")
    return value * _WINDOW_UNIT_MULTIPLIERS[unit]


@dataclass(slots=True)
class SentimentObservation:
    """DTO representing a single sentiment measurement."""

    ts: datetime | None
    polarity: float | None
    confidence: float | None
    zscore: float | None
    aspects: Sequence[str]


class SqlAlchemySentimentRepository:
    """Read sentiment timeseries using SQLAlchemy sessions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def fetch_series(
        self, *, coin: str, window_minutes: int
    ) -> tuple[list[SentimentObservation], datetime | None]:
        stmt = (
            select(
                Sentiment.ts,
                Sentiment.polarity,
                Sentiment.confidence,
                Sentiment.zscore,
                Sentiment.aspects,
                Article.published_ts,
            )
            .join(Article, Sentiment.article_id == Article.id)
            .where(Sentiment.coin == coin)
            .where(Sentiment.zscore_window == window_minutes)
            .order_by(Sentiment.ts.asc())
        )

        observations: list[SentimentObservation] = []
        last_updated: datetime | None = None

        with self._session_factory() as session:
            for row in session.execute(stmt):
                ts = row.ts or row.published_ts
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)

                polarity = _to_float(row.polarity)
                confidence = _to_float(row.confidence)
                zscore = _to_float(row.zscore)
                aspects = tuple(row.aspects or [])

                observations.append(
                    SentimentObservation(
                        ts=ts,
                        polarity=polarity,
                        confidence=confidence,
                        zscore=zscore,
                        aspects=aspects,
                    )
                )

                if ts is not None and (last_updated is None or ts > last_updated):
                    last_updated = ts

        return observations, last_updated


class SentimentService:
    """High-level interface returning serialized sentiment payloads."""

    def __init__(self, repository: SqlAlchemySentimentRepository) -> None:
        self._repository = repository

    def fetch_series(self, symbol: str, window: str) -> dict[str, Any]:
        coin = _normalize_symbol(symbol)
        window_minutes = _coerce_window(window)

        observations, last_updated = self._repository.fetch_series(
            coin=coin, window_minutes=window_minutes
        )

        if last_updated is None:
            last_updated = datetime.now(UTC)

        series: list[dict[str, Any]] = []
        for observation in observations:
            series.append(
                {
                    "ts": observation.ts,
                    "polarity": observation.polarity,
                    "confidence": observation.confidence,
                    "zscore": observation.zscore,
                    "aspects": list(observation.aspects),
                }
            )

        payload: dict[str, Any] = {
            "symbol": symbol,
            "window": window,
            "series": series,
            "last_updated": last_updated,
        }
        return payload


def create_sentiment_service(settings: ApiSettings) -> SentimentService:
    """Factory that constructs a ``SentimentService`` bound to Postgres."""

    engine = database.create_engine(settings)
    session_maker = database.session_factory(engine)
    repository = SqlAlchemySentimentRepository(session_maker)
    return SentimentService(repository)


__all__ = [
    "SentimentService",
    "SqlAlchemySentimentRepository",
    "create_sentiment_service",
]
