# RAGTrader

[![CI](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml/badge.svg)](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/HBPol/rag-trader/graph/badge.svg?token=)](https://codecov.io/gh/HBPol/rag-trader)

RAGTrader — Retrieve, Reason, Trade. A crypto analytics & strategy prototyping app
that fuses Coinbase price data with scraped crowd/news sentiment, visualizes lead–lag &
causal effects across coins, and lets you describe strategies in natural language to
backtest via a safe Strategy DSL.

## Documentation
- [Project Overview](project_docs/ProjectOverview.md)
- [Requirements Specifications](project_docs/RequirementsSpecifications.md)
- [Project Plan](project_docs/ProjectPlan.md)

## Monorepo Layout

| Path | Purpose |
| --- | --- |
| `api/` | FastAPI service (Python 3.11). Contains settings scaffolding and pytest-based unit tests. |
| `pipelines/` | Batch & streaming jobs (Python 3.11). Hosts the Coinbase OHLCV ingestion job and registry primitives. |
| `web/` | Next.js 14 frontend (TypeScript). Includes layout shell, styling entry point, and Vitest smoke test. |

Each package owns its dependencies (`pyproject.toml` / `package.json`) and test suite so we can
iterate with TDD and keep tooling focused.

## Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- pnpm / npm / yarn for frontend dependencies

### Bootstrap local environments

```bash
# API service (FastAPI)
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest

# Apply database migrations (requires Docker or a reachable Postgres DSN)
python -m ragtrader_api.db

# Pipelines package
cd ../pipelines
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest

# Web package
cd ../web
pnpm install  # or npm install / yarn install
pnpm test
```

### Root Tooling
- **Pre-commit** enforces Ruff, Black, isort, mypy, ESLint, and Prettier.
- Docker Compose services and CI workflows will be introduced in later issues per the
  [project plan](project_docs/ProjectPlan.md).
- **PyCharm + Docker**: add a Docker Compose interpreter pointed at the `api` service so
  editor actions reuse the container runtime. In *Settings → Project → Python Interpreter*,
  click **Add Interpreter… → Docker Compose**, select `docker-compose.yml` (and optionally
  `docker-compose.override.yml` if you want the extra services), choose the **Service** named
  `api`, and keep the default `/usr/local/bin/python` path that PyCharm shows. That binary is the
  interpreter baked into the image that ships with the project, so linting, tests, and run
  configurations inside PyCharm mirror what `docker compose up` executes.

## Quickstart

```bash
# Set up env
cp .env.example .env

# Run with remote Qdrant (Cloud)
docker compose up -d --build

# OR run with local Qdrant (override adds qdrant service + points API to it)
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build

# health checks
curl -f http://localhost:8000/healthz
open http://localhost:5173
```

## Container Images

The repository ships production-ready Dockerfiles for the API and web
applications so the stack can be deployed with Docker Compose or any
other orchestrator:

| Path | Description | Default port |
| --- | --- | --- |
| `api/Dockerfile` | Multi-stage Python image that installs dependencies into a virtual environment and serves the FastAPI app via Uvicorn. | `8000` |
| `web/Dockerfile` | Multi-stage Node.js image that builds the Next.js frontend and runs it with `next start`. | `5173` |

Both images honour the environment variables defined in
`.env.example` (such as `API_PORT`, `WEB_PORT`, `RAGTRADER_API_POSTGRES_DSN`, and
`VITE_API_BASE_URL`) so you can tailor behaviour via `.env` or Compose
overrides without rebuilding the containers.

## Coinbase OHLCV ingestion job

The pipelines package exposes `ragtrader_pipelines.coinbase` which fetches
Coinbase candles and upserts them into the API database. Run it locally or
schedule it via Cloud Scheduler:

```bash
cd pipelines
python -m ragtrader_pipelines.coinbase \
  --symbols BTC-USD,ETH-USD \
  --granularity MIN_60 \
  --lookback-minutes 360 \
  --database-url "postgresql+psycopg://user:pass@localhost:5432/ragtrader"
```

The job enforces idempotent writes via SQLAlchemy’s `ON CONFLICT` upsert and
defaults to hourly candles, matching the `ohlcv` schema defined in the API
service.
