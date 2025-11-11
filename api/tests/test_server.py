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
                    ("GET", "/analytics/leadlag"): Response(
                        status_code=200, json={"endpoint": "leadlag"}
                    ),
                    ("GET", "/analytics/correlation"): Response(
                        status_code=200, json={"endpoint": "correlation"}
                    ),
                    ("GET", "/analytics/granger"): Response(
                        status_code=503, json={"endpoint": "granger"}
                    ),
                    ("GET", "/analytics/influence-graph"): Response(
                        status_code=200, json={"endpoint": "influence"}
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
        leadlag_response = await routes["/analytics/leadlag"].endpoint()
        correlation_response = await routes["/analytics/correlation"].endpoint()
        granger_response = await routes["/analytics/granger"].endpoint()
        influence_response = await routes["/analytics/influence-graph"].endpoint()

        assert stub.calls == [
            ("GET", "/healthz"),
            ("GET", "/readyz"),
            ("GET", "/analytics/leadlag"),
            ("GET", "/analytics/correlation"),
            ("GET", "/analytics/granger"),
            ("GET", "/analytics/influence-graph"),
        ]

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

        assert isinstance(leadlag_response, JSONResponse)
        assert json.loads(leadlag_response.body.decode("utf-8")) == {
            "endpoint": "leadlag"
        }

        assert isinstance(correlation_response, JSONResponse)
        assert json.loads(correlation_response.body.decode("utf-8")) == {
            "endpoint": "correlation"
        }

        assert isinstance(granger_response, JSONResponse)
        assert granger_response.status_code == 503
        assert json.loads(granger_response.body.decode("utf-8")) == {
            "endpoint": "granger"
        }

        assert isinstance(influence_response, JSONResponse)
        assert json.loads(influence_response.body.decode("utf-8")) == {
            "endpoint": "influence"
        }

    asyncio.run(run_test())


def test_fastapi_routes_propagate_analytics_errors(
    server_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run_test() -> None:
        class StubMiniApp:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def dispatch(self, method: str, path: str) -> Response:
                key = (method, path)
                self.calls.append(key)
                if path.startswith("/analytics/"):
                    payload = {
                        "status": "error",
                        "freshness": {"age_minutes": None},
                        "message": "Analytics data is unavailable; "
                        "upstream pipelines have not produced results yet.",
                    }
                    return Response(status_code=503, json=payload)
                raise AssertionError(f"Unexpected route dispatched: {key}")

        stub = StubMiniApp()
        monkeypatch.setattr(server_module, "create_app", lambda: stub)

        fastapi_app = server_module.create_fastapi_app()
        routes = {
            route.path: route
            for route in fastapi_app.router.routes
            if isinstance(route, APIRoute)
        }

        leadlag_response = await routes["/analytics/leadlag"].endpoint()
        correlation_response = await routes["/analytics/correlation"].endpoint()
        granger_response = await routes["/analytics/granger"].endpoint()
        influence_response = await routes["/analytics/influence-graph"].endpoint()

        assert stub.calls == [
            ("GET", "/analytics/leadlag"),
            ("GET", "/analytics/correlation"),
            ("GET", "/analytics/granger"),
            ("GET", "/analytics/influence-graph"),
        ]

        for response in (
            leadlag_response,
            correlation_response,
            granger_response,
            influence_response,
        ):
            assert isinstance(response, JSONResponse)
            assert response.status_code == 503
            payload = json.loads(response.body.decode("utf-8"))
            assert payload["status"] == "error"
            assert payload.get("freshness", {}).get("age_minutes") is None
            assert "unavailable" in payload.get("message", "").lower()

    asyncio.run(run_test())
