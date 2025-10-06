# RAGTrader API

This package houses the FastAPI application and related services for the
RAGTrader platform. The implementation will evolve in later issues; for
now we focus on configuration plumbing and health/readiness scaffolding
to enable TDD for subsequent tasks.

## Configuration Summary

The settings model reads environment variables using the
`RAGTRADER_API_` prefix. Required knobs today include:

| Variable | Description |
| --- | --- |
| `RAGTRADER_API_POSTGRES_DSN` | PostgreSQL DSN used by the service when database access is required. Uses the `postgresql+psycopg://` driver string. |
| `RAGTRADER_API_REQUIRE_DATABASE` | Set to `false` to skip enforcing a database DSN in local tests. |
| `RAGTRADER_API_QDRANT_URL` | Base URL for the Qdrant vector store. |
| `RAGTRADER_API_QDRANT_API_KEY` | API key used when connecting to Qdrant Cloud. Ignored for self-hosted deployments. |
| `RAGTRADER_API_USE_QDRANT_CLOUD` | Set to `false` to target a self-hosted Qdrant instance without authentication. |
| `RAGTRADER_API_REQUIRE_VECTOR_STORE` | Set to `false` to bypass vector store readiness checks. |

The default environment is `dev`, with additional allowed values of
`staging` and `prod`.

`.env.example` contains a ready-to-use DSN targeting the docker-compose
Postgres service; copy it into your `.env` to get started quickly.

## Health Endpoints

The lightweight application harness exposes two operational endpoints:

| Route | Semantics |
| --- | --- |
| `GET /healthz` | Returns a JSON payload with service metadata (name, version, environment). |
| `GET /readyz` | Evaluates configuration checks (database, vector store) and returns HTTP 503 if any fail. |

## Development

```bash
# create and activate a virtual environment of your choice, then
pip install -e .[dev]
pytest
```

## Vector store repository

The package exposes a lightweight helper around the Qdrant Python client
to centralize connection retries and feature flag handling. When cloud
mode is enabled (the default), the repository injects the API key from
`ApiSettings`; disabling cloud mode switches the client to a plain
self-hosted URL without authentication.

```python
from ragtrader_api.settings import ApiSettings
from ragtrader_api.vectorstore import VectorStoreRepository

settings = ApiSettings(
    postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
    qdrant_url="https://YOUR-CLUSTER.example",
    qdrant_api_key="<api key>",
)

repository = VectorStoreRepository(settings)
repository.create_collection("documents", vectors_config={"size": 768, "distance": "Cosine"})
repository.upsert_points("documents", points=[{"id": 1, "vector": [...], "payload": {...}}])
```

Use `RAGTRADER_API_USE_QDRANT_CLOUD=false` and omit the API key to target a
local or self-hosted instance. All CRUD helpers automatically retry
transient network failures using an exponential backoff.

### Database workflows

```bash
# Apply migrations using the configured DSN
python -m ragtrader_api.db

# Run integration tests that exercise Postgres + Alembic
pytest tests/test_database.py
```
