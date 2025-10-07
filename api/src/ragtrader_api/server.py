"""ASGI entrypoint that adapts the internal mini-app to FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .app import Response as MiniResponse
from .app import create_app


def _adapt_response(payload: MiniResponse) -> JSONResponse:
    """Convert the mini-application's response into a FastAPI response."""

    return JSONResponse(status_code=payload.status_code, content=payload.json)


def create_fastapi_app() -> FastAPI:
    """Instantiate the FastAPI app wired to the internal mini-app."""

    mini_app = create_app()
    fastapi_app = FastAPI(title="RAGTrader API")

    @fastapi_app.get("/healthz")
    async def healthz() -> JSONResponse:  # pragma: no cover - via integration tests
        return _adapt_response(mini_app.dispatch("GET", "/healthz"))

    @fastapi_app.get("/readyz")
    async def readyz() -> JSONResponse:  # pragma: no cover - via integration tests
        return _adapt_response(mini_app.dispatch("GET", "/readyz"))

    return fastapi_app


app = create_fastapi_app()

__all__ = ["app", "create_fastapi_app"]
