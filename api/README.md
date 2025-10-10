# RAGTrader API

This package houses the FastAPI application and supporting services for the
RAGTrader platform. It currently bundles the database helpers, Alembic
migration CLI, and the health/readiness endpoints that keep ingestion
pipelines operational while the broader implementation evolves.

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
Postgres service; copy it into your `.env` to get started quickly. The
settings loader now reads that file automatically (or an override
specified via `RAGTRADER_API_ENV_FILE`) before evaluating environment
variables, while still letting explicit exports take precedence. When
`RAGTRADER_API_POSTGRES_DSN` is omitted and the database requirement is
enabled (the default), the API will synthesize a DSN using the
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and
`POSTGRES_PASSWORD` variables. You must still provide either the complete
DSN or each of the underlying `POSTGRES_*` variables before the service
starts.

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
PYTHONPATH=src pytest --cov=ragtrader_api --cov-report=term --cov-report=xml --cov-fail-under=80
```

Set `PYTHONPATH=src` so pytest resolves the package the same way CI does before enforcing the
80 percent coverage gate.

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

* Migration helpers live in `src/ragtrader_api/db/migrations/__init__.py`.
* The CLI entry point (`python -m ragtrader_api.db`) resolves to
  `src/ragtrader_api/db/__main__.py`.
