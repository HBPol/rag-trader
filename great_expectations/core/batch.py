"""Runtime batch request primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeBatchRequest:
    """Simplified representation of a runtime batch request."""

    datasource_name: str
    data_connector_name: str
    data_asset_name: str
    runtime_parameters: dict[str, Any]
    batch_identifiers: dict[str, Any]


__all__ = ["RuntimeBatchRequest"]
