"""High-level analytics service for API endpoints."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from .db.repositories.analytics import (
    FeatureRecord,
    GrangerTestRecord,
    LeadLagRecord,
    create_analytics_repository,
)
from .settings import ApiSettings, SettingsValidationError


class AnalyticsRepositoryProtocol(Protocol):
    """Protocol describing the analytics repository methods used by the API."""

    def list_features(
        self,
        *,
        symbol: str,
        feature_name: str,
        limit: int | None = None,
    ) -> list[FeatureRecord]: ...

    def list_lead_lag(
        self,
        *,
        leader: str | None = None,
        follower: str | None = None,
        window: str | None = None,
        limit: int | None = None,
    ) -> list[LeadLagRecord]: ...

    def list_granger_tests(
        self,
        *,
        x_symbol: str | None = None,
        y_symbol: str | None = None,
        window: str | None = None,
        direction: str | None = None,
        limit: int | None = None,
    ) -> list[GrangerTestRecord]: ...


def _ensure_utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _decimal_to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _now() -> datetime:
    return datetime.now(UTC)


class AnalyticsService:
    """Compose analytics payloads backed by the SQLAlchemy repositories."""

    def __init__(
        self,
        *,
        settings: ApiSettings,
        repository: AnalyticsRepositoryProtocol,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._clock = clock or _now

        self._pairs: tuple[str, ...] = tuple(settings.analytics_pairs)
        self._windows: tuple[str, ...] = tuple(settings.analytics_windows)
        self._correlation_metric: str = settings.analytics_correlation_metric
        self._max_age_minutes: int = settings.analytics_max_age_minutes
        self._fallback_minutes: int = settings.analytics_fallback_minutes
        self._granger_significance: float = settings.analytics_granger_significance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def lead_lag(self) -> tuple[int, dict[str, Any]]:
        records = self._repository.list_lead_lag()

        payload_records: list[dict[str, Any]] = []
        last_updated: datetime | None = None
        for record in records:
            computed = _ensure_utc(record.computed_ts)
            if computed is not None:
                last_updated = self._max_dt(last_updated, computed)
            payload_records.append(
                {
                    "leader": record.leader,
                    "follower": record.follower,
                    "window": record.window,
                    "best_lag_minutes": record.best_lag_min,
                    "strength": _decimal_to_float(record.strength),
                    "computed_ts": computed.isoformat() if computed else None,
                }
            )

        status_code, status, freshness, message, iso_last_updated = self._metadata(
            last_updated
        )

        payload: dict[str, Any] = {
            "status": status,
            "data": payload_records,
            "last_updated": iso_last_updated,
            "freshness": freshness,
        }
        if message and status != "ok":
            payload["message"] = message

        return status_code, payload

    def correlation(self) -> tuple[int, dict[str, Any]]:
        entries, last_updated, _ = self._collect_correlation_entries()

        status_code, status, freshness, message, iso_last_updated = self._metadata(
            last_updated
        )
        payload: dict[str, Any] = {
            "status": status,
            "metric": self._correlation_metric,
            "data": entries,
            "last_updated": iso_last_updated,
            "freshness": freshness,
        }
        if message and status != "ok":
            payload["message"] = message

        return status_code, payload

    def granger(self) -> tuple[int, dict[str, Any]]:
        records = self._repository.list_granger_tests()

        payload_records: list[dict[str, Any]] = []
        last_updated: datetime | None = None
        for record in records:
            computed = _ensure_utc(record.computed_ts)
            if computed is not None:
                last_updated = self._max_dt(last_updated, computed)
            source, target = self._resolve_granger_direction(record)
            p_value = _decimal_to_float(record.p_value)
            reject_null = None
            if p_value is not None:
                reject_null = p_value < self._granger_significance

            payload_records.append(
                {
                    "source": source,
                    "target": target,
                    "window": record.window,
                    "direction": record.direction,
                    "p_value": p_value,
                    "reject_null": reject_null,
                    "computed_ts": computed.isoformat() if computed else None,
                }
            )

        status_code, status, freshness, message, iso_last_updated = self._metadata(
            last_updated
        )
        payload: dict[str, Any] = {
            "status": status,
            "data": payload_records,
            "last_updated": iso_last_updated,
            "freshness": freshness,
        }
        if message and status != "ok":
            payload["message"] = message

        return status_code, payload

    def influence_graph(self) -> tuple[int, dict[str, Any]]:
        lead_lag_records = self._repository.list_lead_lag()
        correlations, corr_last_updated, correlation_map = (
            self._collect_correlation_entries()
        )
        granger_records = self._repository.list_granger_tests()

        last_updated: datetime | None = None
        if corr_last_updated is not None:
            last_updated = self._max_dt(last_updated, corr_last_updated)

        granger_map, granger_last_updated = self._build_granger_map(granger_records)
        if granger_last_updated is not None:
            last_updated = self._max_dt(last_updated, granger_last_updated)

        nodes: set[str] = set()
        edges: list[dict[str, Any]] = []

        for record in lead_lag_records:
            nodes.add(record.leader)
            nodes.add(record.follower)

            computed = _ensure_utc(record.computed_ts)
            if computed is not None:
                last_updated = self._max_dt(last_updated, computed)

            corr_value, corr_ts = correlation_map.get(
                (record.leader, record.follower, record.window), (None, None)
            )
            if corr_ts is not None:
                last_updated = self._max_dt(last_updated, corr_ts)

            granger_info = granger_map.get(
                (record.leader, record.follower, record.window)
            )
            if granger_info is not None and granger_info.timestamp is not None:
                last_updated = self._max_dt(last_updated, granger_info.timestamp)

            cross_corr = _decimal_to_float(record.strength)
            metrics: list[float] = []
            if corr_value is not None:
                metrics.append(abs(corr_value))
            if cross_corr is not None:
                metrics.append(abs(cross_corr))
            if granger_info is not None and granger_info.p_value is not None:
                metrics.append(1.0 - min(1.0, granger_info.p_value))

            weight: float | None
            if metrics:
                weight = sum(metrics) / len(metrics)
            else:
                weight = None

            edges.append(
                {
                    "source": record.leader,
                    "target": record.follower,
                    "window": record.window,
                    "lag": record.best_lag_min,
                    "correlation": corr_value,
                    "cross_correlation": cross_corr,
                    "granger_p_value": (
                        None if granger_info is None else granger_info.p_value
                    ),
                    "granger_reject_null": (
                        None if granger_info is None else granger_info.reject_null
                    ),
                    "weight": weight,
                    "computed_ts": computed.isoformat() if computed else None,
                }
            )

        # Add nodes derived only from correlation/Granger data when no lead/lag exists.
        for entry in correlations:
            pair = entry.get("pair", [])
            if isinstance(pair, Sequence) and len(pair) == 2:
                nodes.add(str(pair[0]))
                nodes.add(str(pair[1]))

        for info in granger_map.values():
            nodes.add(info.source)
            nodes.add(info.target)

        edges.sort(key=lambda edge: (edge.get("weight") or 0.0), reverse=True)

        status_code, status, freshness, message, iso_last_updated = self._metadata(
            last_updated
        )
        payload: dict[str, Any] = {
            "status": status,
            "graph": {
                "nodes": sorted(nodes),
                "edges": edges,
            },
            "last_updated": iso_last_updated,
            "freshness": freshness,
        }
        if message and status != "ok":
            payload["message"] = message

        return status_code, payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _metadata(
        self, last_updated: datetime | None
    ) -> tuple[int, str, dict[str, float], str | None, str | None]:
        if last_updated is None:
            return (
                503,
                "error",
                {"age_minutes": float("inf")},
                "Analytics data is unavailable; \
                upstream pipelines have not produced results yet.",
                None,
            )

        normalized = _ensure_utc(last_updated)
        assert normalized is not None  # for mypy
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        age_minutes = max(0.0, (now - normalized).total_seconds() / 60)
        freshness = {"age_minutes": age_minutes}

        if age_minutes <= self._max_age_minutes:
            return 200, "ok", freshness, None, normalized.isoformat()

        if age_minutes <= self._fallback_minutes:
            message = (
                "Analytics results are stale; returning the most recent cached values."
            )
            return 200, "stale", freshness, message, normalized.isoformat()

        message = "Analytics data is older than the configured fallback window \
                   and cannot be served."
        return 503, "error", freshness, message, normalized.isoformat()

    def _max_dt(
        self, current: datetime | None, candidate: datetime | None
    ) -> datetime | None:
        if candidate is None:
            return current
        if current is None:
            return candidate
        return candidate if candidate > current else current

    def _configured_pairs(self) -> tuple[str, ...]:
        if self._pairs:
            return self._pairs

        discovered: dict[str, None] = {}
        for record in self._repository.list_lead_lag():
            discovered[f"{record.leader}-{record.follower}"] = None
            discovered[f"{record.follower}-{record.leader}"] = None
        return tuple(discovered)

    def _collect_correlation_entries(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        datetime | None,
        dict[tuple[str, str, str], tuple[float | None, datetime | None]],
    ]:
        entries: list[dict[str, Any]] = []
        last_updated: datetime | None = None
        value_map: dict[tuple[str, str, str], tuple[float | None, datetime | None]] = {}

        for pair in self._configured_pairs():
            base, quote = self._split_pair(pair)
            symbol = f"{base}-{quote}"
            for window in self._windows:
                feature_name = f"correlation:{self._correlation_metric}:{window}"
                records = self._repository.list_features(
                    symbol=symbol, feature_name=feature_name
                )
                if not records:
                    continue
                record = records[-1]
                ts = _ensure_utc(record.ts)
                if ts is not None:
                    last_updated = self._max_dt(last_updated, ts)
                value = _decimal_to_float(record.value)
                entries.append(
                    {
                        "pair": [base, quote],
                        "window": window,
                        "value": value,
                        "computed_ts": ts.isoformat() if ts else None,
                    }
                )
                value_map[(base, quote, window)] = (value, ts)
                value_map[(quote, base, window)] = (value, ts)

        return entries, last_updated, value_map

    def _build_granger_map(
        self, records: Sequence[GrangerTestRecord]
    ) -> tuple[dict[tuple[str, str, str], _GrangerEdge], datetime | None]:
        mapped: dict[tuple[str, str, str], _GrangerEdge] = {}
        last_updated: datetime | None = None

        for record in records:
            computed = _ensure_utc(record.computed_ts)
            if computed is not None:
                last_updated = self._max_dt(last_updated, computed)
            source, target = self._resolve_granger_direction(record)
            p_value = _decimal_to_float(record.p_value)
            reject = None
            if p_value is not None:
                reject = p_value < self._granger_significance
            edge = _GrangerEdge(
                source=source,
                target=target,
                window=record.window,
                p_value=p_value,
                reject_null=reject,
                timestamp=computed,
            )
            mapped[(source, target, record.window)] = edge

        return mapped, last_updated

    @staticmethod
    def _split_pair(pair: str) -> tuple[str, str]:
        normalized = pair.replace("/", "-").replace(":", "-")
        if "-" not in normalized:
            raise ValueError("Pair values must include a separator (e.g. BTC-ETH).")
        base, quote = normalized.split("-", 1)
        return base.strip().upper(), quote.strip().upper()

    @staticmethod
    def _resolve_granger_direction(record: GrangerTestRecord) -> tuple[str, str]:
        direction = (record.direction or "").lower()
        if "y->x" in direction or "y_to_x" in direction:
            return record.y_symbol, record.x_symbol
        return record.x_symbol, record.y_symbol


class _GrangerEdge:
    """Container describing a directional Granger edge used in influence graph."""

    __slots__ = ("source", "target", "window", "p_value", "reject_null", "timestamp")

    def __init__(
        self,
        *,
        source: str,
        target: str,
        window: str,
        p_value: float | None,
        reject_null: bool | None,
        timestamp: datetime | None,
    ) -> None:
        self.source = source
        self.target = target
        self.window = window
        self.p_value = p_value
        self.reject_null = reject_null
        self.timestamp = timestamp


def create_analytics_service(settings: ApiSettings) -> AnalyticsService:
    """Factory that constructs an ``AnalyticsService`` bound to the database."""

    if settings.require_database and settings.postgres_dsn is None:
        raise SettingsValidationError(
            "Postgres DSN is required to serve analytics endpoints."
        )

    repository = create_analytics_repository(settings)
    return AnalyticsService(settings=settings, repository=repository)


__all__ = [
    "AnalyticsService",
    "AnalyticsRepositoryProtocol",
    "create_analytics_service",
]
