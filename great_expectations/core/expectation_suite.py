"""Expectation suite models used in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass
class ExpectationConfiguration:
    """Represent a single expectation entry."""

    expectation_type: str
    kwargs: Dict[str, Any]


@dataclass
class ExpectationSuite:
    """Lightweight container for expectation configurations."""

    expectation_suite_name: str
    expectations: List[ExpectationConfiguration] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        expectation_suite_name: str,
        expectations: Iterable[Dict[str, Any]],
        meta: Dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        self.expectation_suite_name = expectation_suite_name
        self.expectations = [
            ExpectationConfiguration(
                expectation_type=item.get("expectation_type", ""),
                kwargs=item.get("kwargs", {}),
            )
            for item in expectations
        ]
        self.meta = dict(meta or {})


__all__ = ["ExpectationConfiguration", "ExpectationSuite"]
