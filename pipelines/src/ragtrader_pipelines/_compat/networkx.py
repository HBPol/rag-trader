"""Fallback utilities for environments without the real networkx package."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any


class DiGraph:
    """Minimal directed graph implementation compatible with networkx APIs."""

    def __init__(self) -> None:
        self._nodes: dict[Any, dict[str, Any]] = {}
        self._adjacency: dict[Any, dict[Any, dict[str, Any]]] = defaultdict(dict)

    def add_nodes_from(self, nodes: Iterable[Any]) -> None:
        """Add nodes to the graph, ignoring duplicates."""

        for node in nodes:
            self._nodes.setdefault(node, {})
            self._adjacency.setdefault(node, {})

    def add_edge(self, source: Any, target: Any, **attributes: Any) -> None:
        """Add a directed edge with the provided attributes."""

        self._nodes.setdefault(source, {})
        self._nodes.setdefault(target, {})
        self._adjacency.setdefault(source, {})[target] = dict(attributes)

    def edges(self, data: bool = False) -> Iterator[Any]:
        """Iterate over edges optionally including their attribute dictionaries."""

        for source, targets in self._adjacency.items():
            for target, attributes in targets.items():
                if data:
                    yield (source, target, attributes)
                else:
                    yield (source, target)


__all__ = ["DiGraph"]
