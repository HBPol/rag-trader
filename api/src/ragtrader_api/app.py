"""Minimal application scaffolding for the API service.

This placeholder mimics a subset of the FastAPI contract so that tests
can exercise the health and readiness endpoints without external
packages. When third-party dependencies become available the internal
implementation can be swapped with a real FastAPI app while preserving
the public helpers exposed here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol, cast
from urllib.parse import parse_qsl, urlsplit

from .analytics import create_analytics_service
from .sentiment import create_sentiment_service
from .settings import (
    ApiSettings,
    SchedulerSettings,
    SettingsValidationError,
    get_settings,
)

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    pass


class _JobProtocol(Protocol):  # pragma: no cover - runtime duck typing
    def run(
        self,
        *,
        symbols: tuple[str, ...],
        granularity: Any,
        lookback: timedelta,
    ) -> None:
        """Execute the job."""


JobFactory = Callable[[ApiSettings, SchedulerSettings], _JobProtocol]


@dataclass(slots=True)
class Response:
    """Simple representation of an HTTP response payload."""

    status_code: int
    json: dict[str, Any]


AnalyticsHandler = Callable[[], tuple[int, dict[str, Any]]]


class MiniApp:
    """Extremely small routing harness used for tests."""

    def __init__(
        self,
        settings: ApiSettings,
        *,
        job_factory: JobFactory | None = None,
    ) -> None:
        self.settings = settings
        self._routes: dict[
            tuple[str, str], Callable[[dict[str, str] | None], Response]
        ] = {}
        self._job_factory: JobFactory = job_factory or _default_job_factory
        self._register_default_routes()

    def _register_default_routes(self) -> None:
        self.add_route("GET", "/healthz", self._healthz)
        self.add_route("GET", "/readyz", self._readyz)
        self.add_route("POST", "/jobs/poll_ohlcv", self._poll_coinbase_ohlcv_job)
        self.add_route("GET", "/sentiment", self._get_sentiment)
        self.add_route("GET", "/analytics/leadlag", self._get_lead_lag)
        self.add_route("GET", "/analytics/correlation", self._get_correlation)
        self.add_route("GET", "/analytics/granger", self._get_granger)
        self.add_route("GET", "/analytics/influence-graph", self._get_influence_graph)

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable[[dict[str, str] | None], Response],
    ) -> None:
        self._routes[(method.upper(), path)] = handler

    def dispatch(self, method: str, path: str) -> Response:
        split = urlsplit(path)
        normalized_path = split.path or "/"
        try:
            handler = self._routes[(method.upper(), normalized_path)]
        except KeyError as exc:  # pragma: no cover - guardrail for tests
            raise ValueError(f"Route {method} {path} is not registered") from exc
        query_items = dict(parse_qsl(split.query, keep_blank_values=False))
        return handler(query_items or None)

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------
    def _healthz(self, _: dict[str, str] | None = None) -> Response:
        return Response(status_code=200, json=self.settings.health_payload())

    def _readyz(self, _: dict[str, str] | None = None) -> Response:
        checks = self.settings.readiness_checks()
        status_code = 200 if all(checks.values()) else 503
        payload: dict[str, Any] = {
            "status": "ok" if status_code == 200 else "error",
            "checks": checks,
        }
        return Response(status_code=status_code, json=payload)

    def _poll_coinbase_ohlcv_job(self, _: dict[str, str] | None = None) -> Response:
        try:
            scheduler = self.settings.scheduler_options()
        except SettingsValidationError as exc:
            return Response(
                status_code=500,
                json={
                    "status": "error",
                    "message": str(exc),
                },
            )

        job = self._job_factory(self.settings, scheduler)
        job.run(
            symbols=scheduler.symbols,
            granularity=scheduler.granularity,
            lookback=scheduler.lookback,
        )

        payload = {
            "status": "accepted",
            "symbols": list(scheduler.symbols),
            "granularity": scheduler.granularity.label,
            "lookback_minutes": int(scheduler.lookback.total_seconds() // 60),
        }
        return Response(status_code=202, json=payload)

    def _get_sentiment(self, query: dict[str, str] | None = None) -> Response:
        params = query or {}
        symbol = params.get("symbol")
        window = params.get("window")

        missing = [
            name
            for name, value in (("symbol", symbol), ("window", window))
            if not value
        ]
        if missing:
            missing_csv = ", ".join(missing)
            return Response(
                status_code=400,
                json={
                    "status": "error",
                    "message": f"Missing required query parameters: {missing_csv}.",
                },
            )

        try:
            service = create_sentiment_service(self.settings)
        except SettingsValidationError as exc:
            return Response(
                status_code=500,
                json={"status": "error", "message": str(exc)},
            )

        assert symbol is not None  # for mypy - guarded above
        assert window is not None

        try:
            payload = service.fetch_series(symbol, window)
        except ValueError as exc:
            return Response(
                status_code=400,
                json={"status": "error", "message": str(exc)},
            )

        serialized: dict[str, Any] = {
            key: value for key, value in payload.items() if key != "series"
        }

        series_payload = []
        for item in payload.get("series", []):
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            ts_value = entry.get("ts")
            if isinstance(ts_value, datetime):
                entry["ts"] = ts_value.isoformat()
            series_payload.append(entry)
        serialized["series"] = series_payload

        last_updated_raw = payload.get("last_updated")
        freshness: dict[str, Any]
        if isinstance(last_updated_raw, datetime):
            last_updated = last_updated_raw
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=UTC)
            else:
                last_updated = last_updated.astimezone(UTC)
            serialized["last_updated"] = last_updated.isoformat()
            age_seconds = (datetime.now(UTC) - last_updated).total_seconds()
            if age_seconds < 0:
                age_seconds = 0
            age_minutes = age_seconds / 60
            freshness = {"age_minutes": age_minutes}
        else:
            serialized["last_updated"] = None
            freshness = {"age_minutes": float("inf")}

        serialized["freshness"] = freshness

        if freshness["age_minutes"] > 10:
            serialized.setdefault("status", "error")
            serialized.setdefault("message", "Sentiment data is stale.")
            return Response(status_code=503, json=serialized)

        serialized.setdefault("status", "ok")
        return Response(status_code=200, json=serialized)

    def _invoke_analytics(self, handler: str) -> tuple[int, dict[str, Any]] | Response:
        try:
            service = create_analytics_service(self.settings)
        except SettingsValidationError as exc:
            return Response(
                status_code=500, json={"status": "error", "message": str(exc)}
            )

        method = cast(AnalyticsHandler, getattr(service, handler))
        return method()

    def _get_lead_lag(self, _: dict[str, str] | None = None) -> Response:
        result = self._invoke_analytics("lead_lag")
        if isinstance(result, Response):
            return result
        status, payload = result
        return Response(status_code=status, json=payload)

    def _get_correlation(self, _: dict[str, str] | None = None) -> Response:
        result = self._invoke_analytics("correlation")
        if isinstance(result, Response):
            return result
        status, payload = result
        return Response(status_code=status, json=payload)

    def _get_granger(self, _: dict[str, str] | None = None) -> Response:
        result = self._invoke_analytics("granger")
        if isinstance(result, Response):
            return result
        status, payload = result
        return Response(status_code=status, json=payload)

    def _get_influence_graph(self, _: dict[str, str] | None = None) -> Response:
        result = self._invoke_analytics("influence_graph")
        if isinstance(result, Response):
            return result
        status, payload = result
        return Response(status_code=status, json=payload)


def _default_job_factory(
    settings: ApiSettings, scheduler: SchedulerSettings
) -> _JobProtocol:  # pragma: no cover - exercised via integration tests
    from ragtrader_pipelines.coinbase import (
        CoinbaseClient,
        CoinbaseOhlcvIngestion,
        SqlAlchemyCandleRepository,
    )

    repository = SqlAlchemyCandleRepository.from_dsn(scheduler.database_dsn)
    client = CoinbaseClient()
    return CoinbaseOhlcvIngestion(client=client, repository=repository)


def create_app(
    *,
    settings: ApiSettings | None = None,
    job_factory: JobFactory | None = None,
) -> MiniApp:
    """Construct the minimal application used in tests."""

    resolved = settings if settings is not None else get_settings()
    return MiniApp(settings=resolved, job_factory=job_factory)


__all__ = ["MiniApp", "Response", "create_app", "create_sentiment_service"]
