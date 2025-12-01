"""Parity and smoke tests for Docker Compose configuration."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
COMPOSE_FILES = sorted(REPO_ROOT.glob("docker-compose*.yml"))
QDRANT_COMPOSE_FILE = "docker-compose.qdrant.yml"
REQUIRED_ENV_VARS = {
    "API_PORT",
    "WEB_PORT",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "RAGTRADER_API_POSTGRES_DSN",
    "RAGTRADER_API_QDRANT_URL",
    "RAGTRADER_API_QDRANT_COLLECTION",
    "QDRANT_URL",
    "NEXT_PUBLIC_API_BASE_URL",
}


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple .env style file into a dictionary."""

    env: dict[str, str] = {}
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        key, value = match.groups()
        env[key] = value
    return env


def load_compose_file(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def environment_to_dict(environment: Iterable[Any]) -> dict[str, str]:
    env_map: dict[str, str] = {}
    if isinstance(environment, dict):
        for key, value in environment.items():
            env_map[str(key)] = "" if value is None else str(value)
        return env_map

    for item in environment:
        if isinstance(item, str):
            key, _, value = item.partition("=")
            env_map[key] = value
    return env_map


@pytest.fixture(scope="module")
def env_example() -> dict[str, str]:
    return parse_env_file(ENV_EXAMPLE)


@pytest.fixture(scope="module")
def compose_configs() -> dict[str, dict[str, Any]]:
    configs = {path.name: load_compose_file(path) for path in COMPOSE_FILES}
    assert (
        QDRANT_COMPOSE_FILE in configs
    ), "Expected to load the opt-in Qdrant Compose descriptor."
    return configs


def run_docker(
    docker_path: str, args: Sequence[str], **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    docker_executable = Path(docker_path)
    if not docker_executable.is_absolute():
        msg = f"Docker path must be absolute, got: {docker_path!r}"
        raise ValueError(msg)
    if docker_executable.name not in {"docker", "docker.exe"}:
        msg = f"Unexpected docker executable: {docker_executable.name!r}"
        raise ValueError(msg)

    docker_args = ["docker", *[str(arg) for arg in args]]
    # The command vector is static within the test suite to ensure predictable
    # execution.
    return subprocess.run(  # noqa: S603
        docker_args,
        executable=docker_executable.as_posix(),
        shell=False,
        **kwargs,
    )


def test_env_example_defines_required_variables(env_example: dict[str, str]) -> None:
    missing = REQUIRED_ENV_VARS - env_example.keys()
    assert not missing, f"Missing required variables in .env.example: {missing}"
    dsn = env_example["RAGTRADER_API_POSTGRES_DSN"]
    assert "${POSTGRES_HOST}" in dsn
    assert "${POSTGRES_PORT}" in dsn
    assert "${POSTGRES_DB}" in dsn
    assert env_example["RAGTRADER_API_QDRANT_URL"] == "${QDRANT_URL}"
    assert env_example["RAGTRADER_API_QDRANT_COLLECTION"] == "rag-cluster"


def test_compose_ports_use_env_overrides(
    compose_configs: dict[str, dict[str, Any]],
) -> None:
    base = compose_configs["docker-compose.yml"]
    services = base["services"]
    assert "${POSTGRES_PORT:-5432}:5432" in services["postgres"]["ports"]
    assert "${API_PORT:-8000}:8000" in services["api"]["ports"]
    assert "${WEB_PORT:-5173}:5173" in services["web"]["ports"]


def test_api_service_forwards_database_and_qdrant_settings(
    compose_configs: dict[str, dict[str, Any]],
) -> None:
    base_env = environment_to_dict(
        compose_configs["docker-compose.yml"]["services"]["api"]["environment"]
    )
    assert "${RAGTRADER_API_POSTGRES_DSN" in base_env["RAGTRADER_API_POSTGRES_DSN"]
    assert "${RAGTRADER_API_QDRANT_URL" in base_env["RAGTRADER_API_QDRANT_URL"]
    assert (
        base_env["RAGTRADER_API_QDRANT_COLLECTION"]
        == "${RAGTRADER_API_QDRANT_COLLECTION:-rag-cluster}"
    )

    override_env = environment_to_dict(
        compose_configs[QDRANT_COMPOSE_FILE]["services"]["api"]["environment"]
    )
    assert override_env["RAGTRADER_API_QDRANT_URL"] == "http://qdrant:6333"
    assert (
        override_env["RAGTRADER_API_USE_QDRANT_CLOUD"]
        == "${RAGTRADER_API_USE_QDRANT_CLOUD:-false}"
    )


def test_web_service_forwards_browser_accessible_api_url(
    compose_configs: dict[str, dict[str, Any]],
) -> None:
    web_config = compose_configs["docker-compose.yml"]["services"]["web"]
    build_args = web_config["build"]["args"]
    environment = environment_to_dict(web_config["environment"])

    expected = "${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}"
    assert build_args["NEXT_PUBLIC_API_BASE_URL"] == expected
    assert environment["NEXT_PUBLIC_API_BASE_URL"] == expected


@pytest.mark.smoke
def test_compose_stack_smoke() -> None:
    docker_path = shutil.which("docker")
    if docker_path is None:
        pytest.skip("Docker is not available on this system.")

    compose_base_args = [
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        QDRANT_COMPOSE_FILE,
    ]

    env = os.environ.copy()
    env.update(
        {
            "API_PORT": "18080",
            "WEB_PORT": "15173",
            "POSTGRES_PORT": "15432",
            "RAGTRADER_API_USE_QDRANT_CLOUD": "false",
        }
    )

    env_path = REPO_ROOT / ".env"
    created_env = False
    if not env_path.exists():
        env_path.write_text(ENV_EXAMPLE.read_text())
        created_env = True

    try:
        run_docker(
            docker_path,
            [*compose_base_args, "down", "-v"],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        run_docker(
            docker_path,
            [*compose_base_args, "up", "-d", "--build"],
            cwd=REPO_ROOT,
            env=env,
            check=True,
        )

        wait_for_container_health("ragtrader-postgres", env, docker_path)
        wait_for_container_health("ragtrader-qdrant", env, docker_path)
        wait_for_url(f"http://localhost:{env['API_PORT']}/healthz")
        wait_for_url("http://localhost:6333")
    finally:
        run_docker(
            docker_path,
            [*compose_base_args, "down", "-v"],
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        if created_env and env_path.exists():
            env_path.unlink()


def wait_for_container_health(
    container_name: str, env: dict[str, str], docker_path: str, timeout: float = 120.0
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run_docker(
            docker_path,
            ("inspect", "-f", "{{.State.Health.Status}}", container_name),
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "healthy":
            return
        time.sleep(2)
    raise AssertionError(
        f"Container {container_name} did not become healthy within {timeout} seconds."
    )


def wait_for_url(url: str, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if 200 <= response.status_code < 500:
                return
        except (
            requests.RequestException
        ) as exc:  # pragma: no cover - network failure path
            last_error = exc
        time.sleep(2)
    if last_error is not None:
        raise AssertionError(f"Timed out waiting for {url}: {last_error}")
    raise AssertionError(f"Timed out waiting for {url} to respond.")
