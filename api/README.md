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
| `RAGTRADER_API_POSTGRES_DSN` | PostgreSQL DSN used by the service when database access is required. |
| `RAGTRADER_API_QDRANT_URL` | Base URL for the Qdrant vector store. |
| `RAGTRADER_API_REQUIRE_DATABASE` | Set to `false` to skip enforcing a database DSN in local tests. |
| `RAGTRADER_API_REQUIRE_VECTOR_STORE` | Set to `false` to bypass vector store readiness checks. |

The default environment is `dev`, with additional allowed values of
`staging` and `prod`.

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
