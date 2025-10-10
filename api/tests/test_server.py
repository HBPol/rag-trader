"""Unit tests for the FastAPI server adapter."""

from __future__ import annotations

import asyncio
import importlib
import json
from types import ModuleType

import pytest

try:
    from fastapi.responses import JSONResponse
    from fastapi.routing import APIRoute
except ModuleNotFoundError:  # pragma: no cover - executed in pared-down test env
    pytest.skip(
        "FastAPI is not installed; skipping server tests.",
        allow_module_level=True,
    )

from ragtrader_api.app import Response


@pytest.fixture()
def server_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the FastAPI server module with relaxed dependency requirements."""

    monkeypatch.setenv("RAGTRADER_API_REQUIRE_DATABASE", "0")
    monkeypatch.setenv("RAGTRADER_API_REQUIRE_VECTOR_STORE", "0")
    monkeypatch.setenv("RAGTRADER_API_USE_QDRANT_CLOUD", "0")

    from ragtrader_api.settings import get_settings

    get_settings.cache_clear()

    module = importlib.import_module("ragtrader_api.server")
    importlib.reload(module)

    yield module

    get_settings.cache_clear()
    importlib.reload(module)

    monkeypatch.delenv("RAGTRADER_API_REQUIRE_DATABASE", raising=False)
    monkeypatch.delenv("RAGTRADER_API_REQUIRE_VECTOR_STORE", raising=False)
    monkeypatch.delenv("RAGTRADER_API_USE_QDRANT_CLOUD", raising=False)


def test_adapt_response_returns_json_response(server_module: ModuleType) -> None:
    payload = Response(status_code=201, json={"message": "created"})

    response = server_module._adapt_response(payload)

    assert isinstance(response, JSONResponse)
    assert response.status_code == payload.status_code
    assert json.loads(response.body.decode("utf-8")) == payload.json


def test_fastapi_routes_delegate_to_mini_app(
    server_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run_test() -> None:
        class StubMiniApp:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []
                self.responses = {
                    ("GET", "/healthz"): Response(
                        status_code=200, json={"endpoint": "health"}
                    ),
                    ("GET", "/readyz"): Response(
                        status_code=503, json={"endpoint": "ready"}
                    ),
                }

            def dispatch(self, method: str, path: str) -> Response:
                key = (method, path)
                self.calls.append(key)
                return self.responses[key]

        stub = StubMiniApp()
        monkeypatch.setattr(server_module, "create_app", lambda: stub)

        fastapi_app = server_module.create_fastapi_app()
        routes = {
            route.path: route
            for route in fastapi_app.router.routes
            if isinstance(route, APIRoute)
        }

        health_response = await routes["/healthz"].endpoint()
        ready_response = await routes["/readyz"].endpoint()

        assert stub.calls == [("GET", "/healthz"), ("GET", "/readyz")]

        assert isinstance(health_response, JSONResponse)
        assert health_response.status_code == 200
        assert json.loads(health_response.body.decode("utf-8")) == {
            "endpoint": "health"
        }

        assert isinstance(ready_response, JSONResponse)
        assert ready_response.status_code == 503
        assert json.loads(ready_response.body.decode("utf-8")) == {
            "endpoint": "ready",
        }

    asyncio.run(run_test())
