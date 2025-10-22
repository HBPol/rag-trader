"""Simplified data context primitives used in tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd

from ..core.expectation_suite import ExpectationSuite
from .types.base import DataContextConfig


class AbstractDataContext:
    """Minimal base class placeholder for compatibility."""

    config: DataContextConfig


@dataclass
class BatchDefinition:
    """Capture metadata about a validated batch."""

    batch_identifiers: Dict[str, Any]


class Validator:
    """Evaluate expectation suites against pandas data frames."""

    def __init__(self, dataframe: pd.DataFrame, expectation_suite: ExpectationSuite, *, batch_definition: BatchDefinition) -> None:
        self._dataframe = dataframe
        self._expectation_suite = expectation_suite
        self.active_batch_definition = batch_definition

    def validate(self) -> bool:
        from .context import evaluate_expectation_suite

        return evaluate_expectation_suite(self._dataframe, self._expectation_suite)


__all__ = [
    "AbstractDataContext",
    "BatchDefinition",
    "Validator",
]
