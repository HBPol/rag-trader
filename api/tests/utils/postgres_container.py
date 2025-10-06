"""Custom Postgres container helper for integration tests."""

from __future__ import annotations

from typing import Any, Final

from testcontainers.core.generic import DockerContainer

try:  # pragma: no cover - import fallback logic for various testcontainers versions
    from testcontainers.core.waiting import LogMessageWaitStrategy
except ImportError:  # pragma: no cover - maintain compatibility with older versions
    try:
        from testcontainers.core.waiting_utils import LogMessageWaitStrategy
    except ImportError:  # pragma: no cover - legacy package layout
        try:
            from testcontainers.waiting import LogMessageWaitStrategy
        except ImportError:  # pragma: no cover - last-resort shim for environments without the class

            class LogMessageWaitStrategy:  # type: ignore[override]
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
                    wait_kwargs: dict[str, Any] = {"stream": self._stream}
                    if self._timeout is not None:
                        wait_kwargs["timeout"] = self._timeout
                    container.wait_for_logs(self._message, **wait_kwargs)

                # Modern testcontainers expects wait strategies to expose
                # ``wait_until_ready``; fall back to ``wait`` for compatibility.
                def wait_until_ready(self, container: DockerContainer) -> None:  # pragma: no cover - shim passthrough
                    self.wait(container)

POSTGRES_IMAGE: Final[str] = "postgres:15-alpine"
POSTGRES_DB: Final[str] = "test"
POSTGRES_USER: Final[str] = "test"
POSTGRES_PASSWORD: Final[str] = "test"
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

    def get_connection_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(POSTGRES_PORT)
        return f"postgresql://{self._user}:{self._password}@{host}:{port}/{self._database}"
