# RAGTrader

[![CI](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml/badge.svg)](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/HBPol/rag-trader/graph/badge.svg?token=)](https://codecov.io/gh/HBPol/rag-trader)

RAGTrader - Retrieve, Reason, Trade. A crypto analytics &amp; strategy prototyping app
that fuses Coinbase price data with scraped crowd/news sentiment, visualizes lead–lag &amp; causal effects across coins,
and lets you describe strategies in natural language to backtest via a safe Strategy DSL.

## Features

## Documentation
- [Project Overview](project_docs/ProjectOverview.md)
- [Requirements Specifications](project_docs/RequirementsSpecifications.md)
- [Project Plan](project_docs/ProjectPlan.md)

## Stack

## Quickstart
```bash
# Set up env
cp .env.example .env
# (edit QDRANT_URL/QDRANT_API_KEY, etc.)
# Run with remote Qdrant (Cloud)
docker compose up -d --build
# OR run with local Qdrant (override adds qdrant service + points API to it)
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build
# health checks
curl -f http://localhost:8000/healthz
open http://localhost:5173
```