"""Custom Postgres test container helpers."""

from __future__ import annotations

from testcontainers.core.generic import DockerContainer
from testcontainers.core.waiting_utils import LogMessageWaitStrategy


class PostgresTestContainer(DockerContainer):
    """Docker container tailored for Postgres integration tests."""

    def __init__(self, image: str = "postgres:15-alpine", **kwargs: object) -> None:
        super().__init__(image=image, **kwargs)
        self.with_env("POSTGRES_DB", "test")
        self.with_env("POSTGRES_USER", "test")
        self.with_env("POSTGRES_PASSWORD", "test")
        self.with_exposed_ports(5432)
        self.wait_strategy = LogMessageWaitStrategy(
            "database system is ready to accept connections"
        )

    def get_connection_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(5432)
        return f"postgresql://test:test@{host}:{port}/test"
