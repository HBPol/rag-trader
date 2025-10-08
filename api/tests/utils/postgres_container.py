"""Custom Postgres container helper for integration tests."""

from __future__ import annotations

import os
import socket
import time
from typing import Any, Final

from testcontainers.core.generic import DockerContainer

def _resolve_log_wait_strategy() -> type[Any]:
    try:  # pragma: no cover - import fallback logic for various testcontainers versions
        from testcontainers.core.waiting import (
            LogMessageWaitStrategy as _core_log_wait_strategy,
        )
    except ImportError:  # pragma: no cover - maintain compatibility with older versions
        try:
            from testcontainers.core.waiting_utils import (
                LogMessageWaitStrategy as _waiting_utils_log_wait_strategy,
            )
        except ImportError:  # pragma: no cover - legacy package layout
            try:
                from testcontainers.waiting import (
                    LogMessageWaitStrategy as _legacy_log_wait_strategy,
                )
            except ImportError:  # pragma: no cover - fallback for missing class

                class _shim_log_wait_strategy:  # type: ignore[override]
                    """Minimal shim replicating the log wait strategy API."""

                    def __init__(
                        self,
                        message: str,
                        timeout: float | None = None,
                        stream: str = "stdout",
                        **_: Any,
                    ) -> None:
                        self._message = message
                        self._timeout = timeout
                        self._stream = stream

                    def wait(self, container: DockerContainer) -> None:
                        wrapped = getattr(container, "_container", None)
                        if wrapped is None:
                            raise RuntimeError("Container has not been started yet")

                        deadline: float | None = None
                        if self._timeout is not None:
                            deadline = time.monotonic() + self._timeout

                        poll_interval = 0.1
                        stdout = self._stream != "stderr"
                        stderr = self._stream != "stdout"

                        while True:
                            logs: bytes = wrapped.logs(stdout=stdout, stderr=stderr)
                            decoded = logs.decode("utf-8", errors="ignore")
                            if self._message in decoded:
                                return

                            if deadline is not None and time.monotonic() > deadline:
                                raise TimeoutError(
                                    "Timed out waiting for container log message"
                                )

                            time.sleep(poll_interval)

                    # Modern testcontainers expects wait strategies to expose
                    # ``wait_until_ready``; fall back to ``wait`` for compatibility.
                    def wait_until_ready(
                        self,
                        container: DockerContainer,
                    ) -> None:  # pragma: no cover - shim passthrough
                        self.wait(container)

                _LogMessageWaitStrategy = _shim_log_wait_strategy
            else:
                _LogMessageWaitStrategy = _legacy_log_wait_strategy
        else:
            _LogMessageWaitStrategy = _waiting_utils_log_wait_strategy
    else:
        _LogMessageWaitStrategy = _core_log_wait_strategy

    return _LogMessageWaitStrategy


_LogMessageWaitStrategy = _resolve_log_wait_strategy()


LogMessageWaitStrategy = _LogMessageWaitStrategy


POSTGRES_IMAGE: Final[str] = "postgres:15-alpine"
POSTGRES_DB: Final[str] = "test"
POSTGRES_USER: Final[str] = "test"
POSTGRES_PASSWORD: Final[str] = os.getenv(
    "RAGTRADER_TEST_POSTGRES_PASSWORD",
    "test",
)
POSTGRES_PORT: Final[int] = 5432


class PostgresTestContainer(DockerContainer):
    """Docker container tailored for Postgres integration tests."""

    def __init__(
        self,
        image: str = POSTGRES_IMAGE,
        database: str = POSTGRES_DB,
        user: str = POSTGRES_USER,
        password: str = POSTGRES_PASSWORD,
        port: int = POSTGRES_PORT,
        **kwargs: object,
    ) -> None:
        super().__init__(image=image, **kwargs)
        self._database = database
        self._user = user
        self._password = password
        self._port = port

        self.with_env("POSTGRES_DB", database)
        self.with_env("POSTGRES_USER", user)
        self.with_env("POSTGRES_PASSWORD", password)
        self.with_exposed_ports(port)
        self.waiting_for(
            LogMessageWaitStrategy("database system is ready to accept connections")
        )

    def start(self) -> PostgresTestContainer:  # type: ignore[override]
        super().start()
        self._wait_for_database_ready()
        return self

    def _wait_for_database_ready(self) -> None:
        """Actively wait until Postgres accepts incoming connections."""

        host = self.get_container_host_ip()
        port = int(self.get_exposed_port(self._port))

        # Best-effort TCP probe to ensure the port is reachable even when
        # psycopg is unavailable. This mirrors the behaviour of the
        # ``WaitForLogs`` strategy which blocks until the service is ready.
        tcp_deadline = time.monotonic() + 30
        while True:
            try:
                with socket.create_connection((host, port), timeout=1):
                    break
            except OSError:
                if time.monotonic() >= tcp_deadline:
                    raise TimeoutError(
                        "Timed out waiting for Postgres port to open"
                    ) from None
                time.sleep(0.1)

        try:
            import psycopg
        except ImportError:  # pragma: no cover - optional dependency
            return

        dsn = (
            f"host={host} port={port} dbname={self._database} "
            f"user={self._user} password={self._password}"
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                with psycopg.connect(dsn, connect_timeout=1) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                return
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Timed out waiting for Postgres to accept connections"
                    ) from None
                time.sleep(0.2)

    def get_connection_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(POSTGRES_PORT)
        return (
            f"postgresql://{self._user}:{self._password}@{host}:{port}/{self._database}"
        )
