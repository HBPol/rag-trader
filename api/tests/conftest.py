"""Test configuration for the API package."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINES_SRC = ROOT / "pipelines" / "src"
if PIPELINES_SRC.exists():  # pragma: no cover - exercised in tests
    sys.path.insert(0, str(PIPELINES_SRC))
