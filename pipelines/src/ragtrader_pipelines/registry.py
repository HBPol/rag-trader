"""Registry primitives for pipeline orchestration.

This module gives us a predictable import path that future
jobs can extend while allowing immediate test coverage.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Pipeline = Callable[..., Any]


class PipelineRegistry:
    """Very small registry for named pipelines."""

    def __init__(self) -> None:
        self._pipelines: dict[str, Pipeline] = {}

    def register(self, name: str, pipeline: Pipeline) -> None:
        if name in self._pipelines:
            msg = f"Pipeline '{name}' already registered"
            raise ValueError(msg)
        self._pipelines[name] = pipeline

    def get(self, name: str) -> Pipeline:
        try:
            return self._pipelines[name]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise LookupError(f"Pipeline '{name}' not found") from exc

    def __contains__(self, name: str) -> bool:
        return name in self._pipelines


__all__ = ["PipelineRegistry", "Pipeline"]
