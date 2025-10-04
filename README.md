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
| `pipelines/` | Batch & streaming jobs (Python 3.11). Provides a registry primitive for ingestion tasks. |
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
