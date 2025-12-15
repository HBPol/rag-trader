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

### Development (Docker Compose)
Use the Compose descriptors to mirror production locally or in CI:

- `docker-compose.yml` – default stack targeting Qdrant Cloud.
- `docker-compose.qdrant.yml` – optional local Qdrant override.

Before changing Compose files or `.env.example`, run the smoke tests to confirm health checks stay
aligned:

```bash
pytest tests/test_compose.py
```

## What lives where?
- API settings, health/readiness, and analytics endpoints: see `api/README.md`.
- Pipelines for Coinbase/content ingestion plus analytics jobs and data-quality checks: see
  `pipelines/README.md`.
- Frontend development, UI conventions, and Lighthouse workflow: see `web/README.md`.
