"""Utilities for rendering Cloud Run and Cloud Scheduler commands.

These helpers keep the GitHub Actions deploy workflow declarative while
retaining an easy-to-test rendering layer so we catch regressions to
environment/secret wiring before they reach production.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    image: str
    region: str
    env: dict[str, str]
    secrets: dict[str, str]
    port: int
    allow_unauthenticated: bool = True


@dataclass(frozen=True)
class JobConfig:
    name: str
    image: str
    region: str
    env: dict[str, str]
    secrets: dict[str, str]
    command: str
    args: Iterable[str]


def render_cloud_run_deploy(config: ServiceConfig) -> str:
    env_vars = ",".join(f"{key}={value}" for key, value in config.env.items())
    secret_vars = ",".join(f"{key}={value}" for key, value in config.secrets.items())
    base = [
        "gcloud run deploy",
        config.name,
        f"--image {config.image}",
        f"--region {config.region}",
        f"--port={config.port}",
    ]
    if config.allow_unauthenticated:
        base.append("--allow-unauthenticated")
    if env_vars:
        base.append(f"--set-env-vars {env_vars}")
    if secret_vars:
        base.append(f"--set-secrets {secret_vars}")
    base.append("--quiet")
    return " \\\n    ".join(base)


def render_cloud_run_job(config: JobConfig) -> str:
    env_vars = ",".join(f"{key}={value}" for key, value in config.env.items())
    secret_vars = ",".join(f"{key}={value}" for key, value in config.secrets.items())
    arg_fragment = ",".join(f'"{arg}"' for arg in config.args)
    base = [
        "gcloud run jobs deploy",
        config.name,
        f"--image {config.image}",
        f"--region {config.region}",
        f"--command {config.command}",
        f"--args {arg_fragment}",
    ]
    if env_vars:
        base.append(f"--set-env-vars {env_vars}")
    if secret_vars:
        base.append(f"--set-secrets {secret_vars}")
    base.append("--max-retries=1 --quiet")
    return " \\\n    ".join(base)


def render_scheduler_http_job(
    *,
    name: str,
    region: str,
    project_id: str,
    target_job: str,
    schedule: str,
    service_account: str,
) -> str:
    target = (
        f"https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/"
        f"{project_id}/jobs/{target_job}:run"
    )
    return " ".join(
        [
            "gcloud scheduler jobs create http",
            name,
            f"--location {region}",
            f'--schedule "{schedule}"',
            "--http-method POST",
            f"--uri {target}",
            f"--oauth-service-account-email {service_account}",
            '--headers "Content-Type=application/json"',
            "--message-body '{}'",
            "--max-retry-attempts 1",
            "--attempt-deadline 540s",
            "--quiet",
        ]
    )


__all__ = [
    "ServiceConfig",
    "JobConfig",
    "render_cloud_run_deploy",
    "render_cloud_run_job",
    "render_scheduler_http_job",
]
