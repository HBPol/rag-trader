"""Shared pytest configuration for the pipelines test suite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS = [ROOT, ROOT / "api" / "src", ROOT / "api" / "tests"]

for path in PATHS:
    candidate = str(path)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)
