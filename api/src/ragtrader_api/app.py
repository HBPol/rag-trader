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
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Protocol

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


class MiniApp:
    """Extremely small routing harness used for tests."""

    def __init__(
        self,
        settings: ApiSettings,
        *,
        job_factory: JobFactory | None = None,
    ) -> None:
        self.settings = settings
        self._routes: dict[tuple[str, str], Callable[[], Response]] = {}
        self._job_factory: JobFactory = job_factory or _default_job_factory
        self._register_default_routes()

    def _register_default_routes(self) -> None:
        self.add_route("GET", "/healthz", self._healthz)
        self.add_route("GET", "/readyz", self._readyz)
        self.add_route("POST", "/jobs/poll_ohlcv", self._poll_coinbase_ohlcv_job)

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable[[], Response],
    ) -> None:
        self._routes[(method.upper(), path)] = handler

    def dispatch(self, method: str, path: str) -> Response:
        try:
            handler = self._routes[(method.upper(), path)]
        except KeyError as exc:  # pragma: no cover - guardrail for tests
            raise ValueError(f"Route {method} {path} is not registered") from exc
        return handler()

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------
    def _healthz(self) -> Response:
        return Response(status_code=200, json=self.settings.health_payload())

    def _readyz(self) -> Response:
        checks = self.settings.readiness_checks()
        status_code = 200 if all(checks.values()) else 503
        payload: dict[str, Any] = {
            "status": "ok" if status_code == 200 else "error",
            "checks": checks,
        }
        return Response(status_code=status_code, json=payload)

    def _poll_coinbase_ohlcv_job(self) -> Response:
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


__all__ = ["MiniApp", "Response", "create_app"]
