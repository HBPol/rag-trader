"""Regression tests for the Cloud Run deploy workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

Workflow = dict[str, Any]


def _step_names(job: dict[str, Any]) -> list[str]:
    return [step.get("name", "") for step in job.get("steps", [])]


def _find_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in job.get("steps", []):
        if step.get("name") == name:
            return step
    raise AssertionError(f"Expected to find step named '{name}' in job")


@pytest.fixture(scope="module")
def deploy_workflow() -> Workflow:
    workflow_path = Path(".github/workflows/deploy.yml")
    with workflow_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def deploy_job(deploy_workflow: Workflow) -> dict[str, Any]:
    return deploy_workflow["jobs"]["deploy"]


def test_deploy_workflow_triggers_present(deploy_workflow: Workflow) -> None:
    on_clause = deploy_workflow.get("on", {})
    assert "push" in on_clause and "workflow_dispatch" in on_clause
    push_branches = on_clause["push"].get("branches", [])
    assert "master" in push_branches


def test_images_built_and_pushed(deploy_job: dict[str, Any]) -> None:
    names = _step_names(deploy_job)
    for required in ["Build & push API image", "Build & push Web image"]:
        assert required in names

    api_step = _find_step(deploy_job, "Build & push API image")
    assert "gcloud builds submit" in api_step["run"]
    assert "ragtrader" in api_step["run"]


def test_services_deploy_with_env_and_secrets(deploy_job: dict[str, Any]) -> None:
    api_step = _find_step(deploy_job, "Deploy API service")
    assert '--set-env-vars "ENV=prod' in api_step["run"]
    assert '--set-secrets "DATABASE_URL=DATABASE_URL:latest' in api_step["run"]

    web_step = _find_step(deploy_job, "Deploy Web service")
    assert "NEXT_PUBLIC_API_BASE_URL" in web_step["run"]


def test_jobs_and_scheduler_steps_exist(deploy_job: dict[str, Any]) -> None:
    names = _step_names(deploy_job)
    for required in [
        "Deploy ingestion Cloud Run job",
        "Deploy backtest Cloud Run job",
        "Ensure Scheduler triggers exist",
    ]:
        assert required in names

    scheduler_step = _find_step(deploy_job, "Ensure Scheduler triggers exist")
    assert "apis/run.googleapis.com" in scheduler_step["run"]
    assert "ragtrader-backtest" in scheduler_step["run"]


def test_smoke_tests_hit_healthcheck(deploy_job: dict[str, Any]) -> None:
    smoke_step = _find_step(deploy_job, "Smoke test deployed services")
    assert 'curl -f "${API_URL}/healthz"' in smoke_step["run"]
