"""Data pipelines package placeholder for RAGTrader."""

from importlib.metadata import PackageNotFoundError, version

try:  # pragma: no cover - metadata may be missing in editable installs
    __version__ = version("ragtrader-pipelines")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
