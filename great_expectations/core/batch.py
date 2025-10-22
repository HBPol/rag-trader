"""Runtime batch request primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class RuntimeBatchRequest:
    """Simplified representation of a runtime batch request."""

    datasource_name: str
    data_connector_name: str
    data_asset_name: str
    runtime_parameters: Dict[str, Any]
    batch_identifiers: Dict[str, Any]


__all__ = ["RuntimeBatchRequest"]
