"""ASGI entrypoint that adapts the internal mini-app to FastAPI."""

from __future__ import annotations

import inspect
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .app import Response as MiniResponse
from .app import create_app
from .settings import get_settings


def _adapt_response(payload: MiniResponse) -> JSONResponse:
    """Convert the mini-application's response into a FastAPI response."""

    return JSONResponse(status_code=payload.status_code, content=payload.json)


def create_fastapi_app() -> FastAPI:
    """Instantiate the FastAPI app wired to the internal mini-app."""

    settings = get_settings()
    try:
        signature = inspect.signature(create_app)
    except (TypeError, ValueError):
        signature = None

    accepts_settings = True
    if signature is not None:
        parameters = signature.parameters.values()
        accepts_settings = "settings" in signature.parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters
        )

    if accepts_settings:
        try:
            mini_app = create_app(settings=settings)
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc) or "settings" not in str(
                exc
            ):
                raise
            mini_app = create_app()
    else:
        mini_app = create_app()
    fastapi_app = FastAPI(title="RAGTrader API")

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @fastapi_app.get("/healthz")
    async def healthz() -> JSONResponse:  # pragma: no cover - via integration tests
        return _adapt_response(mini_app.dispatch("GET", "/healthz"))

    @fastapi_app.get("/readyz")
    async def readyz() -> JSONResponse:  # pragma: no cover - via integration tests
        return _adapt_response(mini_app.dispatch("GET", "/readyz"))

    @fastapi_app.get("/sentiment")
    async def sentiment(
        symbol: str | None = None,
        window: str | None = None,
    ) -> JSONResponse:  # pragma: no cover - via integration tests
        query: dict[str, str] = {}
        if symbol is not None:
            query["symbol"] = symbol
        if window is not None:
            query["window"] = window

        path = "/sentiment"
        if query:
            path = f"{path}?{urlencode(query)}"
        return _adapt_response(mini_app.dispatch("GET", path))

    @fastapi_app.get("/analytics/leadlag")
    async def analytics_leadlag() -> JSONResponse:  # pragma: no cover - integration
        return _adapt_response(mini_app.dispatch("GET", "/analytics/leadlag"))

    @fastapi_app.get("/analytics/correlation")
    async def analytics_correlation() -> JSONResponse:  # pragma: no cover - integration
        return _adapt_response(mini_app.dispatch("GET", "/analytics/correlation"))

    @fastapi_app.get("/analytics/granger")
    async def analytics_granger() -> JSONResponse:  # pragma: no cover - integration
        return _adapt_response(mini_app.dispatch("GET", "/analytics/granger"))

    @fastapi_app.get("/analytics/influence-graph")
    async def analytics_influence_graph() -> (
        JSONResponse
    ):  # pragma: no cover - integration
        return _adapt_response(mini_app.dispatch("GET", "/analytics/influence-graph"))

    @fastapi_app.post("/jobs/poll_ohlcv", status_code=202)
    async def jobs_poll_ohlcv() -> JSONResponse:  # pragma: no cover - integration
        return _adapt_response(mini_app.dispatch("POST", "/jobs/poll_ohlcv"))

    return fastapi_app


app = create_fastapi_app()

__all__ = ["app", "create_fastapi_app"]
