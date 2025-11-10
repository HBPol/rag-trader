"""ORM models representing core database tables."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for declarative ORM models."""


class Instrument(Base):
    """Tradable instrument metadata."""

    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    ohlcv: Mapped[list[Ohlcv]] = relationship(back_populates="instrument")
    features: Mapped[list[Feature]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )


class Ohlcv(Base):
    """Open-high-low-close-volume candlesticks."""

    __tablename__ = "ohlcv"
    __table_args__ = (Index("ix_ohlcv_symbol_interval_ts", "symbol", "interval", "ts"),)

    symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("instruments.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    interval: Mapped[str] = mapped_column(String(16), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    instrument: Mapped[Instrument] = relationship(back_populates="ohlcv")


class Article(Base):
    """News article metadata and content."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    published_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    body_excerpt: Mapped[str | None] = mapped_column(Text)
    coins: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        nullable=False,
        server_default=text("'{}'::varchar[]"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    sentiments: Mapped[list[Sentiment]] = relationship(
        "Sentiment",
        back_populates="article",
        cascade="all, delete-orphan",
    )


class Sentiment(Base):
    """Coin sentiment analysis derived from articles."""

    __tablename__ = "sentiments"
    __table_args__ = (
        Index("ix_sentiments_coin_window_ts", "coin", "zscore_window", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    coin: Mapped[str] = mapped_column(String(16), nullable=False)
    polarity: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    aspects: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        server_default=text("'{}'::varchar[]"),
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    zscore_window: Mapped[int] = mapped_column(Integer, nullable=False)
    zscore: Mapped[Decimal | None] = mapped_column(Numeric(10, 5))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    article: Mapped[Article] = relationship("Article", back_populates="sentiments")


class Feature(Base):
    """Computed feature values associated with an instrument."""

    __tablename__ = "features"
    __table_args__ = (
        Index("ix_features_symbol_feature_name_ts", "symbol", "feature_name", "ts"),
    )

    symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("instruments.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    feature_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)

    instrument: Mapped[Instrument] = relationship(
        "Instrument",
        back_populates="features",
    )


class LeadLag(Base):
    """Lead/lag analytics describing leader and follower relationships."""

    __tablename__ = "lead_lag"
    __table_args__ = (
        Index(
            "ix_lead_lag_pair_window_ts",
            "leader",
            "follower",
            "window",
            "computed_ts",
        ),
    )

    leader: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("instruments.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    follower: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("instruments.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    window: Mapped[str] = mapped_column(String(32), primary_key=True)
    computed_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    best_lag_min: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)


class GrangerTest(Base):
    """Granger causality test outcomes between two instruments."""

    __tablename__ = "granger_tests"
    __table_args__ = (
        Index(
            "ix_granger_tests_pair_window_ts",
            "x_symbol",
            "y_symbol",
            "window",
            "computed_ts",
        ),
    )

    x_symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("instruments.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    y_symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("instruments.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    window: Mapped[str] = mapped_column(String(32), primary_key=True)
    computed_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    p_value: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)


__all__ = [
    "Base",
    "Instrument",
    "Ohlcv",
    "Article",
    "Sentiment",
    "Feature",
    "LeadLag",
    "GrangerTest",
]
