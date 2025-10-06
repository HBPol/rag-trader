"""Data pipelines for RAGTrader."""

from importlib.metadata import PackageNotFoundError, version

try:  # pragma: no cover - metadata may be missing in editable installs
    __version__ = version("ragtrader-pipelines")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from .coinbase import (  # noqa: F401 - re-exported for convenience
    CoinbaseClient,
    CoinbaseOhlcvIngestion,
    Granularity,
    OhlcvRecord,
    SqlAlchemyCandleRepository,
)

__all__ = [
    "__version__",
    "CoinbaseClient",
    "CoinbaseOhlcvIngestion",
    "Granularity",
    "OhlcvRecord",
    "SqlAlchemyCandleRepository",
]
