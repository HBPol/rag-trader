"""Database integration helpers for the API service."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from . import database, migrations, models

__all__ = ["database", "migrations", "models", "repositories", "seed_demo"]


def __getattr__(name: str) -> Any:  # pragma: no cover - lazy heavy imports
    if name in {"repositories", "seed_demo"}:
        module = import_module(f"ragtrader_api.db.{name}")
        globals()[name] = module
        return module

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
