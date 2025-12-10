from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.deploy_commands import (  # noqa: E402
    JobConfig,
    ServiceConfig,
    render_cloud_run_deploy,
    render_cloud_run_job,
    render_scheduler_http_job,
)


def test_render_cloud_run_deploy_includes_env_and_secrets() -> None:
    cmd = render_cloud_run_deploy(
        ServiceConfig(
            name="ragtrader-api",
            image="us-docker.pkg.dev/proj/ragtrader/api:sha",
            region="us-central1",
            env={
                "ENV": "prod",
                "COINBASE_API_BASE": "https://api.exchange.coinbase.com",
            },
            secrets={
                "DATABASE_URL": "DATABASE_URL:latest",
                "QDRANT_API_KEY": "QDRANT_API_KEY:latest",
            },
            port=8000,
        )
    )

    assert (
        "--set-env-vars ENV=prod,COINBASE_API_BASE=https://api.exchange.coinbase.com"
        in cmd
    )
    assert (
        "--set-secrets DATABASE_URL=DATABASE_URL:latest,"
        "QDRANT_API_KEY=QDRANT_API_KEY:latest" in cmd
    )
    assert "--port=8000" in cmd
    assert "--allow-unauthenticated" in cmd


def test_render_cloud_run_job_includes_command_and_args() -> None:
    cmd = render_cloud_run_job(
        JobConfig(
            name="ragtrader-ingestion",
            image="us-docker.pkg.dev/proj/ragtrader/api:sha",
            region="us-central1",
            env={"ENV": "prod"},
            secrets={"DATABASE_URL": "DATABASE_URL:latest"},
            command="python",
            args=("-m", "ragtrader_pipelines.coinbase", "--symbols", "BTC,ETH"),
        )
    )

    assert "--command python" in cmd
    assert "ragtrader_pipelines.coinbase" in cmd
    assert "--set-env-vars ENV=prod" in cmd
    assert "--set-secrets DATABASE_URL=DATABASE_URL:latest" in cmd
    assert cmd.endswith("--max-retries=1 --quiet")


def test_render_scheduler_job_targets_cloud_run_job_endpoint() -> None:
    cmd = render_scheduler_http_job(
        name="ragtrader-ingestion",
        region="us-central1",
        project_id="my-project",
        target_job="ragtrader-ingestion",
        schedule="*/15 * * * *",
        service_account="sa@my-project.iam.gserviceaccount.com",
    )

    assert (
        "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/my-project/jobs/ragtrader-ingestion:run"
        in cmd
    )
    assert '--schedule "*/15 * * * *"' in cmd
    assert "--oauth-service-account-email sa@my-project.iam.gserviceaccount.com" in cmd
