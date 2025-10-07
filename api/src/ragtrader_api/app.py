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
from typing import Any

from .settings import ApiSettings, get_settings


@dataclass(slots=True)
class Response:
    """Simple representation of an HTTP response payload."""

    status_code: int
    json: dict[str, Any]


class MiniApp:
    """Extremely small routing harness used for tests."""

    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        self._routes: dict[tuple[str, str], Callable[[], Response]] = {}
        self._register_default_routes()

    def _register_default_routes(self) -> None:
        self.add_route("GET", "/healthz", self._healthz)
        self.add_route("GET", "/readyz", self._readyz)

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


def create_app(*, settings: ApiSettings | None = None) -> MiniApp:
    """Construct the minimal application used in tests."""

    resolved = settings if settings is not None else get_settings()
    return MiniApp(settings=resolved)


__all__ = ["MiniApp", "Response", "create_app"]
