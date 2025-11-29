"""FastAPI routes for strategy translation and backtesting."""

from __future__ import annotations

import base64
import secrets
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from ragtrader_api.strategy import StrategySchema
from ragtrader_api.strategy.nl_to_dsl import (
    NaturalLanguageToDSLConverter,
    StrategyConversionError,
    UnsafeContentError,
)


class BacktestResultProtocol(Protocol):
    """Minimal view of a backtest result returned by an engine."""

    equity_curve: Any
    metrics: Mapping[str, float]


class Backtester(Protocol):
    """Minimal protocol for running backtests from the DSL."""

    def run_backtest(
        self,
        payload: StrategySchema,
        *,
        slippage_bps: float = 0.0,
        fee_bps: float = 0.0,
    ) -> BacktestResultProtocol: ...


security = HTTPBasic()


class _StrategyRequest(BaseModel):
    instructions: str = Field(..., min_length=1)


class _BacktestRequest(BaseModel):
    strategy: StrategySchema
    slippage_bps: float = 0.0
    fee_bps: float = 0.0


@dataclass
class _StoredBacktest:
    metrics: Mapping[str, float]
    equity_curve: list[dict[str, Any]]


class RateLimitExceeded(RuntimeError):
    """Raised when a client exceeds the configured rate limit."""


class RateLimiter:
    """Simple in-memory fixed-window rate limiter."""

    def __init__(self, limit: int = 30, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def hit(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        recent = [ts for ts in self._requests.get(key, []) if ts >= window_start]
        recent.append(now)
        self._requests[key] = recent
        if len(recent) > self.limit:
            raise RateLimitExceeded(
                f"Rate limit exceeded: {self.limit} requests per {self.window_seconds}s"
            )


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Enforce HTTP basic authentication for protected routes."""

    def __init__(self, app: FastAPI, *, username: str, password: str) -> None:
        super().__init__(app)
        self.username = username
        self.password = password

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return self._unauthorized()

        try:
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            provided_user, provided_pass = decoded.split(":", 1)
        except Exception:
            return self._unauthorized()

        if not (
            secrets.compare_digest(provided_user, self.username)
            and secrets.compare_digest(provided_pass, self.password)
        ):
            return self._unauthorized()

        request.state.user = provided_user
        return await call_next(request)

    @staticmethod
    def _unauthorized() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
            content={"detail": "Authentication required"},
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a simple rate limiter to incoming requests."""

    def __init__(self, app: FastAPI, limiter: RateLimiter) -> None:
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        key = getattr(request.state, "user", None)
        if not key:
            client = request.client
            key = client.host if client else "anonymous"
        try:
            self.limiter.hit(str(key))
        except RateLimitExceeded as exc:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": str(exc)},
            )
        return await call_next(request)


def _default_converter_provider() -> NaturalLanguageToDSLConverter:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Strategy converter is not configured",
    )


def _default_backtester_provider() -> Backtester:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Backtester is not configured",
    )


def _serialize_equity(curve: Any) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - pandas may not be installed
        pd = None  # type: ignore

    points: list[dict[str, Any]] = []
    if pd is not None and isinstance(curve, pd.Series):
        for ts, value in curve.items():
            ts_value = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            points.append({"ts": ts_value, "value": float(value)})
        return points

    if isinstance(curve, Mapping):
        for ts, value in curve.items():
            points.append({"ts": str(ts), "value": float(value)})
        return points

    if isinstance(curve, Sequence) and not isinstance(curve, (str, bytes, bytearray)):
        for item in curve:
            if isinstance(item, Mapping):
                ts_value = item.get("ts") or item.get("timestamp")
                value = item.get("value")
                if ts_value is not None and value is not None:
                    points.append({"ts": str(ts_value), "value": float(value)})
                continue
            if isinstance(item, Sequence) and len(item) >= 2:
                ts_value, value = item[0], item[1]
                points.append({"ts": str(ts_value), "value": float(value)})
        return points

    return points


def create_strategy_router(
    *,
    converter_provider=_default_converter_provider,
    backtester_provider=_default_backtester_provider,
) -> APIRouter:
    """Build the strategy router with injectable dependencies."""

    router = APIRouter(prefix="/strategy", tags=["strategy"])

    def get_converter() -> NaturalLanguageToDSLConverter:
        return converter_provider()

    def get_backtester() -> Backtester:
        return backtester_provider()

    @router.post("/nl-to-dsl")
    async def nl_to_dsl(
        payload: _StrategyRequest,
        converter: NaturalLanguageToDSLConverter = Depends(get_converter),
    ) -> Mapping[str, Any]:
        try:
            strategy = converter.convert(payload.instructions)
        except UnsafeContentError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc) or "Request flagged as unsafe",
            ) from exc
        except StrategyConversionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return strategy.model_dump()

    _backtests: dict[str, _StoredBacktest] = {}

    @router.post("/backtests")
    async def run_backtest(
        payload: _BacktestRequest,
        backtester: Backtester = Depends(get_backtester),
    ) -> Mapping[str, Any]:
        result = backtester.run_backtest(
            payload.strategy,
            slippage_bps=payload.slippage_bps,
            fee_bps=payload.fee_bps,
        )
        equity = _serialize_equity(result.equity_curve)
        backtest_id = str(uuid.uuid4())
        _backtests[backtest_id] = _StoredBacktest(
            metrics=dict(result.metrics),
            equity_curve=equity,
        )
        return {
            "backtest_id": backtest_id,
            "metrics": result.metrics,
            "equity_curve": equity,
        }

    def _get_backtest_or_404(backtest_id: str) -> _StoredBacktest:
        try:
            return _backtests[backtest_id]
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found"
            ) from exc

    @router.get("/backtests/{backtest_id}/metrics")
    async def get_backtest_metrics(backtest_id: str) -> Mapping[str, Any]:
        stored = _get_backtest_or_404(backtest_id)
        return {"backtest_id": backtest_id, "metrics": stored.metrics}

    @router.get("/backtests/{backtest_id}/equity")
    async def get_backtest_equity(backtest_id: str) -> Mapping[str, Any]:
        stored = _get_backtest_or_404(backtest_id)
        return {"backtest_id": backtest_id, "equity_curve": stored.equity_curve}

    return router


def create_strategy_app(
    *,
    username: str = "admin",
    password: str = "changeme",
    rate_limit: int = 30,
    window_seconds: int = 60,
    converter_provider=_default_converter_provider,
    backtester_provider=_default_backtester_provider,
) -> FastAPI:
    """Create a standalone FastAPI app for strategy workflows."""

    app = FastAPI(title="RAGTrader Strategy API")
    app.add_middleware(
        RateLimitMiddleware,
        limiter=RateLimiter(limit=rate_limit, window_seconds=window_seconds),
    )
    app.add_middleware(BasicAuthMiddleware, username=username, password=password)
    router = create_strategy_router(
        converter_provider=converter_provider,
        backtester_provider=backtester_provider,
    )
    app.include_router(router)
    return app


__all__ = [
    "Backtester",
    "BacktestResultProtocol",
    "RateLimitExceeded",
    "RateLimiter",
    "create_strategy_app",
    "create_strategy_router",
]
