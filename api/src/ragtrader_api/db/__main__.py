"""Command-line helpers for database maintenance."""

from __future__ import annotations

from ragtrader_api.db import database, migrations
from ragtrader_api.settings import get_settings


def main() -> None:
    """Apply migrations using the configured settings."""

    settings = get_settings()
    engine = database.create_engine(settings)
    migrations.apply_migrations(engine)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
