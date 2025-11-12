# RAGTrader API

This package houses the FastAPI application and supporting services for the
RAGTrader platform. It currently bundles the database helpers, Alembic
migration CLI, and the health/readiness endpoints that keep ingestion
pipelines operational while the broader implementation evolves.

## Analytics dependencies

The API surfaces analytics derived from the pipelines package and now
depends on the shared scientific stack. Installing the project pulls in
`numpy`, `scipy`, `statsmodels`, and `networkx` so the service can load
precomputed artefacts and perform lightweight on-demand calculations.

## Configuration Summary

The settings model reads environment variables using the
`RAGTRADER_API_` prefix. Required knobs today include:

| Variable | Description |
| --- | --- |
| `RAGTRADER_API_POSTGRES_DSN` | PostgreSQL DSN used by the service when database access is required. Uses the `postgresql+psycopg://` driver string. |
| `RAGTRADER_API_REQUIRE_DATABASE` | Set to `false` to skip enforcing a database DSN in local tests. |
| `RAGTRADER_API_QDRANT_URL` | Base URL for the Qdrant vector store. |
| `RAGTRADER_API_QDRANT_API_KEY` | API key used when connecting to Qdrant Cloud. Ignored for self-hosted deployments. Falls back to `QDRANT_API_KEY` when unset. |
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

## Analytics persistence helpers

Statistical artefacts computed by the pipelines package land in the API
database. The new `SqlAlchemyAnalyticsRepository` writes feature vectors,
lead/lag pairs, and Granger causality test results while providing typed
query helpers for API handlers.

```python
from datetime import UTC, datetime
from decimal import Decimal

from ragtrader_api.db import database
from ragtrader_api.db.repositories.analytics import (
    FeatureRecord,
    GrangerTestRecord,
    LeadLagRecord,
    SqlAlchemyAnalyticsRepository,
)
from ragtrader_api.settings import ApiSettings

settings = ApiSettings(postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app")
engine = database.create_engine(settings)
session_factory = database.session_factory(engine)
repository = SqlAlchemyAnalyticsRepository(session_factory)

repository.upsert_features(
    [
        FeatureRecord(
            symbol="BTC",
            feature_name="rsi_14",
            ts=datetime(2024, 1, 1, tzinfo=UTC),
            value=Decimal("54.3210"),
        )
    ]
)

repository.upsert_lead_lag(
    [
        LeadLagRecord(
            leader="BTC",
            follower="ETH",
            window="1h",
            best_lag_min=15,
            strength=Decimal("0.8125"),
            computed_ts=datetime(2024, 1, 1, 1, tzinfo=UTC),
        )
    ]
)

latest = repository.list_granger_tests(direction="x->y", limit=5)
```

Run `python -m ragtrader_api.db.seed_demo` after configuring the Postgres
DSN to load deterministic demo rows into the `features`, `lead_lag`, and
`granger_tests` tables. The helper applies migrations on the fly so a
fresh database is ready for inspection via `psql` or `psycopg` notebooks.

## Analytics API endpoints

The API exposes cached analytics snapshots generated by the pipelines
service. Four read-only routes cover lead/lag, rolling correlations,
Granger causality, and an aggregated influence graph:

```
GET /analytics/leadlag
GET /analytics/correlation
GET /analytics/granger
GET /analytics/influence-graph
```

Each response contains a `status`, `freshness.age_minutes`, and
`last_updated` (ISO-8601) describing when the underlying computation was
produced. When results fall outside the configured freshness window the
service downgrades the response to `status: "stale"` while returning the
last known values. Data older than the fallback horizon yields
`status: "error"` with HTTP 503 so clients can trigger re-computation.

The FastAPI OpenAPI contract is committed to `api/openapi.json` so
reviewers can diff payload shapes alongside code. Regenerate the schema
after modifying any endpoint by running:

```bash
cd api
python tools/generate_openapi.py
```

### Demo analytics payloads

Run `python -m ragtrader_api.db.seed_demo` to load deterministic analytics
rows into Postgres, then query the endpoints above to receive the payloads
demonstrated below. These fixtures make it straightforward to check the
REST responses against [AC-1](../project_docs/RequirementsSpecifications.md#4-acceptance-criteria-summary)
from the acceptance-criteria matrix.

#### `GET /analytics/leadlag`

```json
{
  "status": "ok",
  "last_updated": "2024-01-01T01:00:00+00:00",
  "freshness": {"age_minutes": 0.0},
  "data": [
    {
      "leader": "BTC",
      "follower": "ETH",
      "window": "1h",
      "best_lag_minutes": 15,
      "strength": 0.8125,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    },
    {
      "leader": "ETH",
      "follower": "SOL",
      "window": "1h",
      "best_lag_minutes": 25,
      "strength": 0.6554,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    },
    {
      "leader": "BTC",
      "follower": "ETH",
      "window": "4h",
      "best_lag_minutes": 60,
      "strength": 0.7021,
      "computed_ts": "2024-01-01T00:00:00+00:00"
    }
  ]
}
```

#### `GET /analytics/correlation`

```json
{
  "status": "ok",
  "metric": "pearson",
  "last_updated": "2024-01-01T01:00:00+00:00",
  "freshness": {"age_minutes": 0.0},
  "data": [
    {
      "pair": ["BTC", "ETH"],
      "window": "1h",
      "value": 0.8456,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    },
    {
      "pair": ["ETH", "SOL"],
      "window": "1h",
      "value": -0.3789,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    }
  ]
}
```

#### `GET /analytics/granger`

```json
{
  "status": "ok",
  "last_updated": "2024-01-01T01:00:00+00:00",
  "freshness": {"age_minutes": 0.0},
  "data": [
    {
      "source": "BTC",
      "target": "SOL",
      "window": "1d",
      "direction": "x->y",
      "p_value": 0.0125,
      "reject_null": true,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    },
    {
      "source": "ETH",
      "target": "SOL",
      "window": "1h",
      "direction": "x->y",
      "p_value": 0.0187,
      "reject_null": true,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    },
    {
      "source": "BTC",
      "target": "ETH",
      "window": "1d",
      "direction": "y->x",
      "p_value": 0.221,
      "reject_null": false,
      "computed_ts": "2024-01-01T00:00:00+00:00"
    }
  ]
}
```

#### `GET /analytics/influence-graph`

```json
{
  "status": "ok",
  "last_updated": "2024-01-01T01:00:00+00:00",
  "freshness": {"age_minutes": 0.0},
  "graph": {
    "nodes": ["BTC", "ETH", "SOL"],
    "edges": [
      {
        "source": "BTC",
        "target": "ETH",
        "window": "1h",
        "lag": 15,
        "correlation": 0.8456,
        "cross_correlation": 0.8125,
        "granger_p_value": null,
        "granger_reject_null": null,
        "weight": 0.8291,
        "computed_ts": "2024-01-01T01:00:00+00:00"
      },
      {
        "source": "ETH",
        "target": "SOL",
        "window": "1h",
        "lag": 25,
        "correlation": -0.3789,
        "cross_correlation": 0.6554,
        "granger_p_value": 0.0187,
        "granger_reject_null": true,
        "weight": 0.6719,
        "computed_ts": "2024-01-01T01:00:00+00:00"
      },
      {
        "source": "BTC",
        "target": "ETH",
        "window": "4h",
        "lag": 60,
        "correlation": null,
        "cross_correlation": 0.7021,
        "granger_p_value": null,
        "granger_reject_null": null,
        "weight": 0.7021,
        "computed_ts": "2024-01-01T00:00:00+00:00"
      }
    ]
  }
}
```

### Database workflows

```bash
# Apply migrations using the configured DSN
python -m ragtrader_api.db

# Run integration tests that exercise Postgres + Alembic
pytest tests/test_database.py

# Exercise analytics migrations + repository helpers
pytest tests/test_analytics_persistence.py
```

* Migration helpers live in `src/ragtrader_api/db/migrations/__init__.py`.
* The CLI entry point (`python -m ragtrader_api.db`) resolves to
  `src/ragtrader_api/db/__main__.py`.
