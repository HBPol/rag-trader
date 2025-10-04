"""Configuration primitives for the API service.

The real FastAPI application will extend these settings once
infrastructure is wired. For now we only validate that the
package reads environment variables using pydantic-style models.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class ApiSettings:
    """Minimal settings placeholder for the API service."""

    env: str = "dev"
    postgres_dsn: Optional[str] = None
    qdrant_url: str = "https://example-qdrant"
    root_path: Path = Path("/app")

    def is_configured(self) -> bool:
        """Return ``True`` when the most critical settings are set."""

        return bool(self.postgres_dsn) and self.qdrant_url.startswith("http")


__all__ = ["ApiSettings"]
