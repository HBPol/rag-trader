"""Unit tests for the FastAPI server adapter."""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("fastapi")
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

os.environ.setdefault("RAGTRADER_API_REQUIRE_DATABASE", "0")
os.environ.setdefault("RAGTRADER_API_REQUIRE_VECTOR_STORE", "0")
os.environ.setdefault("RAGTRADER_API_USE_QDRANT_CLOUD", "0")

from ragtrader_api.app import Response
from ragtrader_api import server
from ragtrader_api.server import _adapt_response, create_fastapi_app


def test_adapt_response_returns_json_response() -> None:
    payload = Response(status_code=201, json={"message": "created"})

    response = _adapt_response(payload)

    assert isinstance(response, JSONResponse)
    assert response.status_code == payload.status_code
    assert json.loads(response.body.decode("utf-8")) == payload.json


@pytest.mark.asyncio
async def test_fastapi_routes_delegate_to_mini_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setattr(server, "create_app", lambda: stub)

    fastapi_app = create_fastapi_app()
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
    assert json.loads(health_response.body.decode("utf-8")) == {"endpoint": "health"}

    assert isinstance(ready_response, JSONResponse)
    assert ready_response.status_code == 503
    assert json.loads(ready_response.body.decode("utf-8")) == {"endpoint": "ready"}
