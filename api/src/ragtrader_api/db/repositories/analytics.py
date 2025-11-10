"""Typed repositories for persisting analytics results."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ...settings import ApiSettings
from .. import database
from ..models import Feature, GrangerTest, LeadLag

SessionFactory = sessionmaker[Session]


@dataclass(frozen=True, slots=True)
class FeatureRecord:
    """Payload representing a single feature datapoint."""

    symbol: str
    feature_name: str
    ts: datetime
    value: Decimal


@dataclass(frozen=True, slots=True)
class LeadLagRecord:
    """Payload describing a leader/follower relationship."""

    leader: str
    follower: str
    window: str
    best_lag_min: int
    strength: Decimal
    computed_ts: datetime


@dataclass(frozen=True, slots=True)
class GrangerTestRecord:
    """Payload representing a Granger causality test result."""

    x_symbol: str
    y_symbol: str
    window: str
    p_value: Decimal
    direction: str
    computed_ts: datetime


class SqlAlchemyAnalyticsRepository:
    """Persistence helpers backed by a SQLAlchemy session factory."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def upsert_features(self, records: Iterable[FeatureRecord]) -> None:
        items = list(records)
        if not items:
            return

        with self._session_factory() as session:
            for record in items:
                session.merge(
                    Feature(
                        symbol=record.symbol,
                        feature_name=record.feature_name,
                        ts=record.ts,
                        value=record.value,
                    )
                )
            session.commit()

    def list_features(
        self,
        *,
        symbol: str,
        feature_name: str,
        limit: int | None = None,
    ) -> list[FeatureRecord]:
        stmt = (
            select(Feature)
            .where(Feature.symbol == symbol)
            .where(Feature.feature_name == feature_name)
            .order_by(Feature.ts.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            FeatureRecord(
                symbol=row.symbol,
                feature_name=row.feature_name,
                ts=row.ts,
                value=row.value,
            )
            for row in rows
        ]

    def upsert_lead_lag(self, records: Iterable[LeadLagRecord]) -> None:
        items = list(records)
        if not items:
            return

        with self._session_factory() as session:
            for record in items:
                session.merge(
                    LeadLag(
                        leader=record.leader,
                        follower=record.follower,
                        window=record.window,
                        computed_ts=record.computed_ts,
                        best_lag_min=record.best_lag_min,
                        strength=record.strength,
                    )
                )
            session.commit()

    def list_lead_lag(
        self,
        *,
        leader: str | None = None,
        follower: str | None = None,
        window: str | None = None,
        limit: int | None = None,
    ) -> list[LeadLagRecord]:
        stmt = select(LeadLag).order_by(LeadLag.computed_ts.desc())
        if leader is not None:
            stmt = stmt.where(LeadLag.leader == leader)
        if follower is not None:
            stmt = stmt.where(LeadLag.follower == follower)
        if window is not None:
            stmt = stmt.where(LeadLag.window == window)
        if limit is not None:
            stmt = stmt.limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            LeadLagRecord(
                leader=row.leader,
                follower=row.follower,
                window=row.window,
                best_lag_min=row.best_lag_min,
                strength=row.strength,
                computed_ts=row.computed_ts,
            )
            for row in rows
        ]

    def upsert_granger_tests(self, records: Iterable[GrangerTestRecord]) -> None:
        items = list(records)
        if not items:
            return

        with self._session_factory() as session:
            for record in items:
                session.merge(
                    GrangerTest(
                        x_symbol=record.x_symbol,
                        y_symbol=record.y_symbol,
                        window=record.window,
                        computed_ts=record.computed_ts,
                        p_value=record.p_value,
                        direction=record.direction,
                    )
                )
            session.commit()

    def list_granger_tests(
        self,
        *,
        x_symbol: str | None = None,
        y_symbol: str | None = None,
        window: str | None = None,
        direction: str | None = None,
        limit: int | None = None,
    ) -> list[GrangerTestRecord]:
        stmt = select(GrangerTest).order_by(GrangerTest.computed_ts.desc())
        if x_symbol is not None:
            stmt = stmt.where(GrangerTest.x_symbol == x_symbol)
        if y_symbol is not None:
            stmt = stmt.where(GrangerTest.y_symbol == y_symbol)
        if window is not None:
            stmt = stmt.where(GrangerTest.window == window)
        if direction is not None:
            stmt = stmt.where(GrangerTest.direction == direction)
        if limit is not None:
            stmt = stmt.limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            GrangerTestRecord(
                x_symbol=row.x_symbol,
                y_symbol=row.y_symbol,
                window=row.window,
                p_value=row.p_value,
                direction=row.direction,
                computed_ts=row.computed_ts,
            )
            for row in rows
        ]


def create_analytics_repository(settings: ApiSettings) -> SqlAlchemyAnalyticsRepository:
    """Factory helper that binds the repository to a Postgres engine."""

    engine = database.create_engine(settings)
    session_maker = database.session_factory(engine)
    return SqlAlchemyAnalyticsRepository(session_maker)


__all__: Sequence[str] = [
    "FeatureRecord",
    "LeadLagRecord",
    "GrangerTestRecord",
    "SqlAlchemyAnalyticsRepository",
    "create_analytics_repository",
]
