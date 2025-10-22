"""Checkpoint helpers for the lightweight Great Expectations stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .data_context import AbstractDataContext


@dataclass
class CheckpointResult:
    """Result object returned after running a checkpoint."""

    success: bool


class SimpleCheckpoint:
    """Evaluate one or more validations against a data context."""

    def __init__(self, *, name: str, data_context: AbstractDataContext) -> None:
        self.name = name
        self._data_context = data_context

    def run(self, validations: Iterable[Mapping[str, object]]) -> CheckpointResult:
        overall_success = True
        for validation in validations:
            batch_request = validation["batch_request"]
            expectation_suite_name = validation["expectation_suite_name"]
            result = self._data_context.run_validation(
                batch_request=batch_request,
                expectation_suite_name=expectation_suite_name,
            )
            overall_success &= bool(result)
        return CheckpointResult(success=overall_success)


__all__ = ["CheckpointResult", "SimpleCheckpoint"]
