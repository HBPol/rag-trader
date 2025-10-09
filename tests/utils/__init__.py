"""Utility helpers for the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

from .alembic_stubs import ensure_alembic_sqlalchemy_stubs

SRC_PATH = Path(__file__).resolve().parents[2] / "api" / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

ensure_alembic_sqlalchemy_stubs()

__all__ = ["ensure_alembic_sqlalchemy_stubs"]
