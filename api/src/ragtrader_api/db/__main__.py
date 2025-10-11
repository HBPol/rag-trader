"""Command-line helpers for database maintenance."""

from __future__ import annotations

from sqlalchemy import exc as sa_exc
from sqlalchemy.engine import Engine, make_url

from ragtrader_api.db import database, migrations
from ragtrader_api.settings import get_settings


def main() -> None:
    """Apply migrations using the configured settings.

    The command retries once with ``localhost`` as the Postgres host when the
    initial attempt fails due to a temporary DNS resolution error. This mirrors
    the setup used in docker-compose environments where the DSN may point at the
    ``postgres`` service name.
    """

    settings = get_settings()
    engine = database.create_engine(settings)

    try:
        migrations.apply_migrations(engine)
        return
    except sa_exc.OperationalError as exc:
        postgres_dsn = settings.postgres_dsn
        if postgres_dsn is None:
            raise

        if not _should_retry_with_localhost(exc, postgres_dsn):
            raise

        engine.dispose()

        try:
            retry_engine = _rebuild_engine_with_localhost(postgres_dsn)
        except sa_exc.OperationalError as rebuild_error:
            raise exc from rebuild_error

        try:
            migrations.apply_migrations(retry_engine)
        except sa_exc.OperationalError as retry_error:
            raise exc from retry_error

        finally:
            retry_engine.dispose()


def _should_retry_with_localhost(
    exc: sa_exc.OperationalError, postgres_dsn: str
) -> bool:
    """Return ``True`` when the error is a temporary DNS failure."""

    if exc.orig is None:
        return False

    message = str(exc.orig)
    if "[Errno -3] Temporary failure in name resolution" not in message:
        return False

    url = make_url(postgres_dsn)
    host = url.host

    if host in {None, "localhost"}:
        return False

    return True


def _rebuild_engine_with_localhost(postgres_dsn: str) -> Engine:
    """Create a new engine using ``localhost`` as the host."""

    url = make_url(postgres_dsn).set(host="localhost")
    return database.sa_create_engine(
        url.render_as_string(hide_password=False),
        pool_pre_ping=True,
        future=True,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
