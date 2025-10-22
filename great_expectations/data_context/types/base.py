"""Configuration dataclasses mirroring a subset of Great Expectations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class FilesystemStoreBackendDefaults:
    """Capture filesystem paths for the lightweight data context."""

    root_directory: str


@dataclass
class DataContextConfig:
    """Minimal configuration object stored on the data context."""

    datasources: Dict[str, Any]
    expectations_store_name: str
    validations_store_name: str
    evaluation_parameter_store_name: str
    checkpoint_store_name: str
    store_backend_defaults: FilesystemStoreBackendDefaults
    data_docs_sites: Dict[str, Any]
    anonymous_usage_statistics: Dict[str, Any]


__all__ = ["DataContextConfig", "FilesystemStoreBackendDefaults"]
