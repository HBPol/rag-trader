"""Helper script that writes the FastAPI OpenAPI schema to disk."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
PIPELINES_SRC = PROJECT_ROOT.parent / "pipelines" / "src"


def _configure_environment() -> None:
    if SRC.exists():
        sys.path.insert(0, str(SRC))
    if PIPELINES_SRC.exists():
        sys.path.insert(0, str(PIPELINES_SRC))

    os.environ.setdefault("RAGTRADER_API_REQUIRE_DATABASE", "false")
    os.environ.setdefault("RAGTRADER_API_REQUIRE_VECTOR_STORE", "false")


def _create_app():
    from ragtrader_api.server import create_fastapi_app

    return create_fastapi_app()


def main() -> None:
    _configure_environment()
    app = _create_app()
    schema = app.openapi()

    output_path = PROJECT_ROOT / "openapi.json"
    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote OpenAPI schema to {output_path.relative_to(PROJECT_ROOT.parent)}")


if __name__ == "__main__":
    main()
