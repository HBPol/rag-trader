"""Core package for the RAGTrader API service."""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any

try:  # pragma: no cover - best effort metadata lookup
    __version__ = version("ragtrader-api")
except PackageNotFoundError:  # pragma: no cover - package not installed yet
    __version__ = "0.0.0"


def __getattr__(name: str) -> Any:  # pragma: no cover - lightweight lazy imports
    if name == "AnalyticsService":
        module = import_module("ragtrader_api.analytics")
        value = module.AnalyticsService
    elif name == "VectorStoreRepository":
        module = import_module("ragtrader_api.vectorstore")
        value = module.VectorStoreRepository
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    globals()[name] = value
    return value


__all__ = ["__version__", "AnalyticsService", "VectorStoreRepository"]
