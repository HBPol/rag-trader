"""Minimal stub of the :mod:`great_expectations` package for tests."""

from __future__ import annotations

from .data_context import AbstractDataContext
from .data_context.context import InMemoryDataContext


def get_context(*, project_config, context_root_dir: str) -> AbstractDataContext:
    """Return an in-memory data context for tests.

    The real Great Expectations library exposes a similar factory.  The test
    suite only needs a very small subset of its behaviour, so this function
    simply instantiates the lightweight in-memory context implemented in this
    repository.
    """

    return InMemoryDataContext(
        project_config=project_config, context_root_dir=context_root_dir
    )


__all__ = [
    "get_context",
    "AbstractDataContext",
]
