"""Expectation suite models used in tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExpectationConfiguration:
    """Represent a single expectation entry."""

    expectation_type: str
    kwargs: dict[str, Any]


@dataclass
class ExpectationSuite:
    """Lightweight container for expectation configurations."""

    expectation_suite_name: str
    expectations: list[ExpectationConfiguration] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        expectation_suite_name: str,
        expectations: Iterable[dict[str, Any]],
        meta: dict[str, Any] | None = None,
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
