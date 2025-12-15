# RAGTrader

[![Monorepo CI](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml/badge.svg)](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/HBPol/rag-trader/graph/badge.svg?token=FE8QZDDHMO)](https://codecov.io/gh/HBPol/rag-trader)

RAGTrader — Retrieve, Reason, Trade. A crypto analytics & strategy prototyping app that fuses
Coinbase price data with scraped crowd/news sentiment, surfaces lead–lag and causal effects, and
lets you express strategies in natural language.

## Documentation map
- [Project Overview](project_docs/ProjectOverview.md)
- [Requirements Specifications](project_docs/RequirementsSpecifications.md)
- [Project Plan](project_docs/ProjectPlan.md)
- [API package](api/README.md)
- [Pipelines package](pipelines/README.md)
- [Web package](web/README.md)

## Monorepo layout
| Path | Purpose |
| --- | --- |
| `api/` | FastAPI service (Python 3.11) with database + vector store integration. |
| `pipelines/` | Batch & streaming jobs for Coinbase OHLCV and sentiment ingestion plus analytics registry. |
| `web/` | Next.js 14 frontend that consumes the API analytics responses. |
| `docker/`, `docker-compose*.yml` | Container entrypoints used for local and production deployments. |
| `tests/` | Compose smoke tests that keep the stack configuration aligned. |

Each package owns its detailed setup and testing instructions inside its README.

## Quickstart (local development)
The fastest way to run the full stack locally:

```bash
cp .env.example .env
# start API, web, Postgres, and Redis against Qdrant Cloud
docker compose up -d --build

# or add a local Qdrant container
docker compose -f docker-compose.yml -f docker-compose.qdrant.yml up -d --build
```

When the containers are healthy, visit `http://localhost:8000/healthz` and `http://localhost:5173`.
Package-specific dev workflows (tests, linting, migrations) live in the linked READMEs above.

## Deployment
### One-time Google Cloud bootstrap
1. **Create/target a GCP project** and enable the Cloud Run, Cloud Build, Artifact Registry,
   Cloud Scheduler, and Secret Manager APIs.
2. **Create an Artifact Registry (Docker) repository** named `ragtrader` in your chosen region
   (e.g., `us-central1-docker.pkg.dev/PROJECT_ID/ragtrader`).
3. **Provision a service account** (e.g., `ragtrader-deployer@PROJECT_ID.iam.gserviceaccount.com`)
   with roles: Cloud Run Admin, Cloud Build Service Account, Artifact Registry Administrator,
   Secret Manager Secret Accessor, and Cloud Scheduler Admin. Grant it Workload Identity
   User on the GitHub OIDC provider if you use GitHub Actions (see below).
4. **Seed Secret Manager** with the runtime secrets referenced by the deploy workflow:
   - `DATABASE_URL` – Postgres DSN for API + jobs
   - `QDRANT_API_KEY` – Qdrant Cloud key
   - `RAGTRADER_STRATEGY_USERNAME` / `RAGTRADER_STRATEGY_PASSWORD` – strategy endpoint auth
   - Optional data ingesters: `CONTENT_REDDIT_CLIENT_ID`, `CONTENT_REDDIT_CLIENT_SECRET`,
     `CONTENT_COINDESK_API_KEY`, `RSS_BASIC_AUTH`
5. **Decide on Qdrant hosting**. For Qdrant Cloud, populate `QDRANT_URL` with the cluster URL and
   keep `RAGTRADER_API_USE_QDRANT_CLOUD=true`; for self-hosted, set `RAGTRADER_API_USE_QDRANT_CLOUD=false`
   and point `RAGTRADER_LOCAL_QDRANT_URL` at your instance.

You can perform steps 1–3 via the CLI—substitute your `PROJECT_ID` and `REGION` values:

```bash
PROJECT_ID=your-project-id
REGION=us-central1

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories create ragtrader \
  --repository-format=docker --location="$REGION" \
  --description="RAGTrader images"

gcloud iam service-accounts create ragtrader-deployer \
  --display-name="RAGTrader deployer"

for ROLE in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.admin \
  roles/secretmanager.secretAccessor roles/cloudscheduler.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:ragtrader-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE"
done
```

After the bootstrap, copy `.env.example` to `.env` and fill in the placeholders (Postgres, Qdrant,
strategy, scheduler, and content ingestion). The same file can be exported to Cloud Run via
`--set-env-vars` or Terraform to keep staging/prod aligned with local development.

### Production (Cloud Run / GCP)
Build once, push to Artifact Registry, and deploy the containers to Cloud Run. Substitute your
project/region values as needed:

```bash
# API
cd api
gcloud builds submit --tag "gcr.io/PROJECT_ID/ragtrader-api"
gcloud run deploy ragtrader-api --image "gcr.io/PROJECT_ID/ragtrader-api" \
  --region REGION --allow-unauthenticated --port 8000 --set-env-vars "$(cat ../.env | tr "\n" ",")"

# Web
cd ../web
gcloud builds submit --tag "gcr.io/PROJECT_ID/ragtrader-web"
gcloud run deploy ragtrader-web --image "gcr.io/PROJECT_ID/ragtrader-web" \
  --region REGION --allow-unauthenticated --port 5173 --set-env-vars "$(cat ../.env | tr "\n" ",")"
```

Point `NEXT_PUBLIC_API_BASE_URL` at the public API URL and supply the same environment variables
used locally (Postgres, Qdrant, strategy credentials, etc.).

**Secrets & schedules**: The deploy workflow binds Cloud Run jobs to Secret Manager entries for
`DATABASE_URL`, `QDRANT_API_KEY`, and the strategy credentials, and creates Cloud Scheduler triggers
for ingestion/backtests. Ensure those secrets exist before the workflow runs so the API, pipelines,
and jobs start healthy.

### Development (Docker Compose)
Use the Compose descriptors to mirror production locally or in CI:

- `docker-compose.yml` – default stack targeting Qdrant Cloud.
- `docker-compose.qdrant.yml` – optional local Qdrant override.

Before changing Compose files or `.env.example`, run the smoke tests to confirm health checks stay
aligned:

```bash
pytest tests/test_compose.py
```

## GitHub Actions secrets & variables

Populate repository secrets/variables so CI and deployment can succeed:

| Name | Type | Purpose |
| --- | --- | --- |
| `GCP_PROJECT_ID`, `GCP_REGION` | Secret | Used by the deploy workflow to target the right project/region. |
| `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT` | Secret | Configure OIDC + Workload Identity for deploys. |
| `QDRANT_URL`, `QDRANT_API_KEY` | Secret | Reachability + API defaults when targeting Qdrant Cloud. |
| `REACHABILITY_RSS_FEEDS`, `RSS_BASIC_AUTH`, `REACHABILITY_SKIP_QDRANT` | Secret | Inputs for the external reachability probes. |
| `DATABASE_URL` | Secret | Postgres DSN fed into Cloud Run services/jobs. |
| `RAGTRADER_STRATEGY_USERNAME`, `RAGTRADER_STRATEGY_PASSWORD` | Secret | Auth for `/strategy` endpoints and backtests. |
| `CODECOV_TOKEN` | Secret | Required for coverage uploads in CI. |
| `CLOUD_RUN_API_SERVICE`, `CLOUD_RUN_WEB_SERVICE` | Variable (optional) | Override default Cloud Run service names. |

With these values in place and `.env` populated from the example file, the stack comes up locally
via Docker Compose and deploys to Cloud Run with live API/web services plus scheduled ingestion
jobs.

## What lives where?
- API settings, health/readiness, and analytics endpoints: see `api/README.md`.
- Pipelines for Coinbase/content ingestion plus analytics jobs and data-quality checks: see
  `pipelines/README.md`.
- Frontend development, UI conventions, and Lighthouse workflow: see `web/README.md`.
