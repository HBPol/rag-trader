"""Regression tests for the GitHub Actions CI workflow configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")


Workflow = dict[str, Any]


@pytest.fixture(scope="module")
def ci_workflow() -> Workflow:
    """Load the CI workflow file once per test module."""
    workflow_path = Path(".github/workflows/ci.yml")
    with workflow_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def python_quality_job(ci_workflow: Workflow) -> dict[str, Any]:
    return ci_workflow["jobs"]["python-quality"]


@pytest.fixture(scope="module")
def node_quality_job(ci_workflow: Workflow) -> dict[str, Any]:
    return ci_workflow["jobs"]["node-quality"]


@pytest.fixture(scope="module")
def vitest_config_text() -> str:
    return Path("web/vitest.config.ts").read_text(encoding="utf-8")


def _step_names(job: dict[str, Any]) -> list[str]:
    return [step.get("name", "") for step in job.get("steps", [])]


def _find_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in job.get("steps", []):
        if step.get("name") == name:
            return step
    raise AssertionError(f"Expected to find step named '{name}' in job")


def test_ci_jobs_present(ci_workflow: Workflow) -> None:
    jobs = ci_workflow.get("jobs", {})
    expected_jobs = {
        "workflow-guardrails",
        "reachability",
        "python-quality",
        "node-quality",
        "compose-smoke",
        "docker-build",
    }
    missing = expected_jobs - set(jobs)
    assert not missing, f"Missing required jobs: {sorted(missing)}"


def test_python_quality_has_static_analysis_steps(
    python_quality_job: dict[str, Any],
) -> None:
    names = _step_names(python_quality_job)
    for required in ["Ruff (lint)", "Ruff format", "mypy"]:
        assert required in names, f"Python quality job missing '{required}' step"


def test_python_quality_pytest_has_coverage_gate(
    python_quality_job: dict[str, Any],
) -> None:
    pytest_step = _find_step(python_quality_job, "Pytest with coverage gate")
    run_command = pytest_step.get("run", "")
    match = re.search(r"--cov-fail-under=(\d+)", run_command)
    assert match is not None, "Pytest command must enforce a coverage threshold"
    assert int(match.group(1)) >= 80, "Backend coverage threshold must be at least 80%"


def test_python_quality_matrix_and_python_version(
    python_quality_job: dict[str, Any],
) -> None:
    matrix = python_quality_job["strategy"]["matrix"]["include"]
    packages = {entry["package"] for entry in matrix}
    assert packages == {"api", "pipelines"}
    for entry in matrix:
        assert "cov_package" in entry, "Each matrix entry must define a cov_package"

    setup_python = _find_step(python_quality_job, "Set up Python")
    assert setup_python["with"]["python-version"] == "3.11"


def test_node_quality_configuration(node_quality_job: dict[str, Any]) -> None:
    names = _step_names(node_quality_job)
    for required in ["ESLint", "TypeScript type check", "Vitest with coverage gate"]:
        assert required in names, f"Node quality job missing '{required}' step"

    setup_node = _find_step(node_quality_job, "Set up Node.js")
    assert setup_node["with"]["node-version"] == "20"


def test_frontend_coverage_thresholds(vitest_config_text: str) -> None:
    thresholds = dict(
        re.findall(
            r"(lines|functions|statements|branches):\s*(\d+)", vitest_config_text
        )
    )
    assert thresholds, "Vitest config must define coverage thresholds"
    for metric, value in thresholds.items():
        assert int(value) >= 70, f"Frontend coverage for {metric} must be at least 70%"


def test_docker_build_job_present(ci_workflow: Workflow) -> None:
    docker_job = ci_workflow["jobs"].get("docker-build")
    assert docker_job is not None, "Docker build job must be defined"
    names = _step_names(docker_job)
    for required in ["Build API image", "Build Web image"]:
        assert required in names, f"Docker build job missing '{required}' step"


def test_reachability_job_runs_probes(ci_workflow: Workflow) -> None:
    reachability = ci_workflow["jobs"]["reachability"]
    run_step = _find_step(reachability, "Run reachability probes")
    assert "tools/reachability.py" in run_step.get("run", ""), (
        "Reachability job must invoke probes script"
    )
