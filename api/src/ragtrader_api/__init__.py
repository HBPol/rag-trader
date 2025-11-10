"""Core package for the RAGTrader API service."""

from importlib.metadata import PackageNotFoundError, version

from .vectorstore import VectorStoreRepository

try:  # pragma: no cover - best effort metadata lookup
    __version__ = version("ragtrader-api")
except PackageNotFoundError:  # pragma: no cover - package not installed yet
    __version__ = "0.0.0"

from .analytics import AnalyticsService

__all__ = ["__version__", "AnalyticsService", "VectorStoreRepository"]
