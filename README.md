# RAGTrader

[![Monorepo CI](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml/badge.svg)](https://github.com/HBPol/rag-trader/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/HBPol/rag-trader/graph/badge.svg?token=FE8QZDDHMO)](https://codecov.io/gh/HBPol/rag-trader)

RAGTrader — Retrieve, Reason, Trade. A crypto analytics & strategy prototyping app
that fuses Coinbase price data with scraped crowd/news sentiment, visualizes lead–lag &
causal effects across coins, and lets you describe strategies in natural language to
backtest via a safe Strategy DSL.

## Documentation
- [Project Overview](project_docs/ProjectOverview.md)
- [Requirements Specifications](project_docs/RequirementsSpecifications.md)
- [Project Plan](project_docs/ProjectPlan.md)

## Content Ingestion & Sentiment

The sentiment pipelines pair modular content adapters (CoinDesk Data API,
social, and long-form sources) with a deduplication cache, a lightweight
sentiment classifier, and a
rolling z-score calculator. Jobs run via the
`ragtrader_pipelines.content` entry point so ingestion, labeling, and
aggregation share configuration and telemetry.

```bash
# Run a 2-hour window locally against Postgres while fetching Reddit + CoinDesk
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/ragtrader"
export CONTENT_REDDIT_CLIENT_ID=...
export CONTENT_REDDIT_CLIENT_SECRET=...
export CONTENT_COINDESK_API_KEY=...
# Optionally override the CoinDesk Data API host if your account uses a regional endpoint
# export CONTENT_COINDESK_BASE_URL="https://regional.data-api.coindesk.com"
python -m ragtrader_pipelines.content \
  --adapters reddit,coindesk \
  --lookback-minutes 120 \
  --freshness-minutes 180 \
  --zscore-window 6
```

The CLI supports additional sources (see `pipelines/src/ragtrader_pipelines/content/sources.py`)
and honors the following environment variables:

- `DATABASE_URL`: SQLAlchemy URL for the ingestion target database.
- `CONTENT_COINDESK_API_KEY`: CoinDesk Data API key (the legacy
  `CONTENT_RSS_COINDESK_API_KEY` name is still accepted for backward
  compatibility).
- `CONTENT_COINDESK_BASE_URL`: Optional CoinDesk Data API host override for
  region-specific tenants (aliases the legacy `CONTENT_RSS_COINDESK_BASE_URL`).
- `CONTENT_REDDIT_CLIENT_ID` / `CONTENT_REDDIT_CLIENT_SECRET`: Reddit API credentials.
- `CONTENT_DEDUPE_URL`: Optional Redis instance to persist the deduplication cache.
- `CONTENT_SENTIMENT_MODEL`: Override the default classifier alias.

Pass `--help` to explore more knobs (batch size, retry/backoff tuning, dry-run mode).

## Analytics batch job

The analytics engine combines Coinbase OHLCV candles with sentiment
z-scores stored in Postgres to compute rolling price-return versus
sentiment correlations, cross-asset lead/lag relationships, and Granger
causality tests. The job runs as a standalone CLI so it can be scheduled
alongside the ingestion pipelines:

```bash
python -m ragtrader_pipelines.analytics_job \
  --start "2024-01-01T00:00:00Z" \
  --end "2024-01-02T00:00:00Z" \
  --symbols BTC,ETH \
  --windows 1h,4h \
  --price-interval 1h \
  --sentiment-window 6 \
  --max-lag-minutes 60 \
  --database-url "postgresql+psycopg://user:pass@localhost:5432/ragtrader"
```

`--windows` accepts a comma-separated list of sampling intervals that
control the resampled series used for both correlation features and the
lead/lag + Granger computations. The job looks up `DATABASE_URL` from the
environment when the flag is omitted, and it exposes registry wiring so
Cloud Scheduler / Airflow can reuse the shared pipeline registry
(`ragtrader_pipelines.analytics_job:register_analytics_job`).

## Monorepo Layout

| Path | Purpose |
| --- | --- |
| `api/` | FastAPI service (Python 3.11). Contains settings scaffolding and pytest-based unit tests. |
| `pipelines/` | Batch & streaming jobs (Python 3.11). Hosts Coinbase OHLCV + content sentiment ingestion jobs and registry primitives. |
| `web/` | Next.js 14 frontend (TypeScript). Includes layout shell, styling entry point, and Vitest smoke test. |

Each package owns its dependencies (`pyproject.toml` / `package.json`) and test suite so we can
iterate with TDD and keep tooling focused.

## Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- pnpm / npm / yarn for frontend dependencies
- Docker Engine + Docker Compose plugin (for the provided stack)
- Copy the root `.env.example` to `.env` so Compose and local tooling share the same configuration

### Bootstrap local environments

```bash
# Create a shared virtual environment for all Python tooling
python -m venv .venv
source .venv/bin/activate

# Install editable packages and root developer requirements
pip install -e api[dev] -e pipelines[dev] -r requirements-dev.txt

# Install frontend dependencies (pnpm shown, npm or yarn also work)
cd web && pnpm install
# Run the Python and frontend test suites with coverage gates
make test

# API service (FastAPI)
cd api
PYTHONPATH=src pytest --cov=ragtrader_api --cov-report=term --cov-report=xml --cov-fail-under=80

# Apply database migrations (requires Docker or a reachable Postgres DSN)
python -m ragtrader_api.db

# Pipelines package
cd ../pipelines
PYTHONPATH=src pytest --cov=ragtrader_pipelines --cov-report=term --cov-report=xml --cov-fail-under=80

# Web package
cd ../web
pnpm install  # or npm install / yarn install
pnpm test -- --coverage  # or run `make test-frontend` from the repository root

# Return to the repository root when finished
cd ..

# Deactivate the shared virtual environment if you no longer need it
deactivate
```

> **Heads-up:** The editable installs for `api/` and `pipelines/` require build
> backends such as `setuptools>=68`. Ensure your environment can reach PyPI (or
> configure an internal mirror / wheelhouse) before running the `pip install`
> step, or pre-install the build requirements manually.

#### Regenerating `web/pnpm-lock.yaml` locally

When network access to the npm registry is unavailable in the remote development
environment, generate the frontend lockfile on a machine that can reach the
registry and then push it to the repository:

1. Install [pnpm](https://pnpm.io/installation) if it is not already available.
2. From the repository root, run:

   ```bash
   cd web
   pnpm install
   ```

   This will create or update `pnpm-lock.yaml` based on `package.json`.
3. Commit the new lockfile alongside any dependency updates:

   ```bash
   git add web/pnpm-lock.yaml
   git commit -m "chore(web): add pnpm lockfile"
   git push
   ```
4. Re-run the frontend checks to confirm everything passes with the lockfile in
   place:

   ```bash
   pnpm install
   pnpm lint
   ```

Keeping the lockfile under version control ensures GitHub Actions continues to
use the pnpm cache configured in `.github/workflows/ci.yml` and that local
installs remain reproducible.

### Root Tooling
- **Pre-commit** enforces Ruff (linting, formatting, and import sorting), mypy, ESLint, and Prettier.
- **Docker Compose & CI** expose the API, web, Postgres, and Redis services (with an optional
  local Qdrant override) described in the [Quickstart](#quickstart), and GitHub Actions already
  runs smoke tests with the stack while we stage deeper pipeline coverage for upcoming CI work.
- **Compose smoke test** ensures `.env.example` and the Docker Compose files stay aligned. Run
  `pytest tests/test_compose.py` before relying on the stack locally or in CI. See [Compose Smoke
  Tests](#compose-smoke-tests) for details on the scenarios covered.
- **External reachability probes** live in [`tools/reachability.py`](tools/reachability.py). They
  verify Coinbase, CoinDesk Data API endpoints, and Qdrant respond before we run heavier jobs. Execute
  `python tools/reachability.py` locally or rely on the "External Reachability" CI job to exercise
  them on every push.

### Analytics data-quality checks

The analytics pipelines rely on [Great Expectations](https://greatexpectations.io/) to validate the
seeded BTC/ETH fixtures that drive Issue #3’s acceptance criteria. Install the optional dependency
before running the suite:

```bash
cd pipelines
pip install -e .[data-quality]  # installs great-expectations and pyarrow
PYTHONPATH=src pytest --no-cov tests/test_analytics_data_quality.py
# Run the Postgres-backed integration test for the analytics job
PYTHONPATH=src pytest --maxfail=1 tests/test_analytics_job_integration.py
```

The expectation suite lives at
[`pipelines/tests/data_quality/analytics_suite.yml`](pipelines/tests/data_quality/analytics_suite.yml)
and encodes the data-quality deliverable called out in Issue #3 (“Data tests (Great Expectations)
for NaNs, gaps, time alignment”). Pass `--no-cov` (or another coverage override) because
`pipelines/pyproject.toml` enforces an 80% coverage gate by default. No additional environment
variables are required—the pytest fixture loads the bundled analytics CSV directly.
- **PyCharm + Docker**: add a Docker Compose interpreter pointed at the `api` service so
  editor actions reuse the container runtime. In *Settings → Project → Python Interpreter*,
  click **Add Interpreter… → Docker Compose**, select `docker-compose.yml` (and optionally
  `docker-compose.qdrant.yml` if you want the extra services), choose the **Service** named
  `api`, and keep the default `/usr/local/bin/python` path that PyCharm shows. That binary is the
  interpreter baked into the image that ships with the project, so linting, tests, and run
  configurations inside PyCharm mirror what `docker compose up` executes.

#### Run pre-commit locally

The root [`.pre-commit-config.yaml`](.pre-commit-config.yaml) defines the exact linting and
formatting jobs that GitHub Actions executes. Python-focused hooks lean on Ruff for linting,
formatting, and import sorting (plus mypy for typing) across the `api/` and `pipelines/`
packages, while the JavaScript/TypeScript hooks (ESLint and Prettier) cover the `web/` app. Run
everything from the repository root before opening a PR—there's no need to `cd` into individual
packages, because `pre-commit run --all-files` mirrors the CI workflow one-for-one. The `ruff-format`
hook now rewrites files in-place during local runs so you get fixed sources automatically, while
CI still verifies that the formatter stays clean via `ruff format --check .`, ensuring bypassed
hooks are caught:

```bash
pre-commit install      # sets up the Git hook using the shared virtualenv
pre-commit run --all-files
```

All hooks now execute in the shared virtualenv described in [Bootstrap local environments](#bootstrap-local-environments).
Bootstrap and activate that environment before running `pre-commit run` so the Python tooling and
dependencies are available without package-specific bootstrapping:

```bash
pip install -e api[dev] -e pipelines[dev] -r requirements-dev.txt
```

Mypy mirrors the GitHub Actions matrix: execute it once from `api/` and once from
`pipelines/` so the service-specific `pyproject.toml` configs load in strict mode.
`pre-commit run mypy-api --all-files` and `pre-commit run mypy-pipelines --all-files` wrap those two
invocations, matching CI exactly:

```bash
cd api && mypy --config-file=pyproject.toml
cd pipelines && mypy --config-file=pyproject.toml
pre-commit run mypy-api --all-files
pre-commit run mypy-pipelines --all-files
```

To re-run a specific hook against the full tree, use the hook's name explicitly. Each hook below is
available via `pre-commit run <hook> --all-files`:

```bash
pre-commit run ruff --all-files           # Python linting + import sorting (Ruff)
pre-commit run ruff-format --all-files    # Python formatting (Ruff formatter, auto-rewrites)
pre-commit run mypy-api --all-files       # Python type checks (api/)
pre-commit run mypy-pipelines --all-files # Python type checks (pipelines/)
pre-commit run eslint --all-files         # Web linting (ESLint)
pre-commit run prettier --all-files       # Web formatting (Prettier)
```

Pre-commit caches environments under `~/.cache/pre-commit`, so subsequent runs are fast and only
touch the files you modified.

### Testing & Coverage

| Area | Local virtualenv / shell | `docker compose exec` equivalent |
| --- | --- | --- |
| API (`ragtrader_api`) | `PYTHONPATH=src pytest --cov=ragtrader_api --cov-report=term --cov-report=xml --cov-fail-under=80` | `docker compose exec api env PYTHONPATH=src pytest --cov=ragtrader_api --cov-report=term --cov-report=xml --cov-fail-under=80` |
| Pipelines (`ragtrader_pipelines`) | `PYTHONPATH=src pytest --cov=ragtrader_pipelines --cov-report=term --cov-report=xml --cov-fail-under=80` | _No dedicated service; run locally or via CI until a pipelines container is added._ |
| Web (`web/`) | `pnpm test -- --coverage` | `docker compose exec web pnpm test -- --coverage` |
| Compose smoke tests | `pytest tests/test_compose.py` | _Run from the host so the test suite can resolve the repository and Compose CLI._ |

Use `make test` from the repository root to execute the API and pipelines suites in sequence with their shared
coverage thresholds. The target expects the editable installs above to be available in the active virtualenv so it
can rely on the same Python environment used by CI.

The coverage invocations match the CI gates (80% minimum for Python packages and full Vitest
coverage reports for the frontend). Run them after `pip install -e .[dev]` (Python) or `pnpm install`
(web) so local tooling mirrors GitHub Actions.

## Quickstart

```bash
# Set up env
cp .env.example .env

# Fill in vector store credentials from Qdrant Cloud so the API can reach your cluster
$EDITOR .env  # set QDRANT_URL and either RAGTRADER_API_QDRANT_API_KEY or QDRANT_API_KEY per .env.example hints

# Validate Compose parity and health checks
pytest tests/test_compose.py

# Run with remote Qdrant (Cloud)
docker compose up -d --build

# OR run fully offline (disables the vector store requirement until you bring one online)
RAGTRADER_API_REQUIRE_VECTOR_STORE=false docker compose up -d --build

# OR run with local Qdrant (override adds qdrant service + points API to it)
docker compose -f docker-compose.yml -f docker-compose.qdrant.yml up -d --build

# health checks
curl -f http://localhost:8000/healthz
open http://localhost:5173
```

> **Notes**
> - You can create or reuse a managed cluster in [Qdrant Cloud](https://qdrant.tech/cloud/) to obtain the `QDRANT_URL` and API key values referenced in `.env.example`. Set `RAGTRADER_API_QDRANT_API_KEY` (preferred) or `QDRANT_API_KEY` to satisfy the cloud credential requirement.
> - The override stack is opt-in: include `-f docker-compose.qdrant.yml` when you want the co-located Qdrant container, or omit it to keep pointing at Qdrant Cloud.
> - The API loads variables from `.env` (or a path provided via `RAGTRADER_API_ENV_FILE`) automatically, while still honouring any explicit environment variables you export.

Once the services report healthy, exercise the FastAPI service at
`http://localhost:8000/docs` or `http://localhost:8000/healthz` and browse the web frontend on
`http://localhost:5173` to confirm the containers are wired together correctly.

### Docker Compose profiles

The repository ships two Compose descriptors:

- `docker-compose.yml` is the baseline stack used in CI smoke tests. It provisions the API,
  frontend, and supporting services that are shared across environments (e.g. Postgres, Redis).
- `docker-compose.qdrant.yml` is opt-in. It swaps the API from using the managed Qdrant Cloud
  endpoint to a co-located Qdrant container so you can iterate entirely offline.

Use the base file on its own when you want to mirror CI or production, where the vector store lives
in Qdrant Cloud. Layer the override file when you want an all-local environment. Both files consume
the variables documented in [Container Images](#container-images) and stay tested via the
[Compose Smoke Tests](#compose-smoke-tests).

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

## Compose Smoke Tests

The regression suite in `tests/test_compose.py` validates that the Docker Compose files, environment
variables, and health checks stay in sync. After updating `.env`, any Dockerfile, or either Compose
descriptor, run:

```bash
pytest tests/test_compose.py
```

The tests boot the stack defined in [`docker-compose.yml`](docker-compose.yml) (optionally layered
  with [`docker-compose.qdrant.yml`](docker-compose.qdrant.yml)) and assert each service's
`/healthz` endpoint responds successfully.

## External reachability probes

[`tools/reachability.py`](tools/reachability.py) provides lightweight HTTP checks for Coinbase,
CoinDesk Data API endpoints, and Qdrant. The script powers the "External Reachability" GitHub Actions job and
can be run manually via:

```bash
python tools/reachability.py
```

The following environment variables control its behaviour (see [`.env.example`](.env.example) for
defaults):

| Variable | Purpose |
| --- | --- |
| `REACHABILITY_SKIP_ALL` | Skip every probe (useful when running CI in a fully offline environment). |
| `REACHABILITY_SKIP_COINBASE` | Skip the Coinbase probe while keeping CoinDesk/Qdrant. |
| `REACHABILITY_SKIP_COINDESK` (alias: `REACHABILITY_SKIP_RSS`) | Skip CoinDesk Data API checks. |
| `REACHABILITY_SKIP_QDRANT` | Skip the Qdrant health check. |
| `REACHABILITY_COINDESK_ENDPOINTS` (alias: `REACHABILITY_RSS_FEEDS`) | Comma-separated list of CoinDesk Data API URLs to probe. |
| `REACHABILITY_COINDESK_BASE_URL` | Override the CoinDesk Data API host used to construct the default probe. |
| `REACHABILITY_COINDESK_ENDPOINT_PATH` | Override the default endpoint path appended to the base URL. |
| `REACHABILITY_QDRANT_URL` | Overrides `QDRANT_URL` for the Qdrant health check, if needed. |
| `REACHABILITY_TIMEOUT_SECONDS` | HTTP timeout applied to each request (defaults to 10 seconds). |
| `REACHABILITY_COINDESK_API_KEY` (aliases: `CONTENT_COINDESK_API_KEY`, `CONTENT_RSS_COINDESK_API_KEY`) | API key forwarded via the `x-api-key` header. |
| `QDRANT_API_KEY` | Optional API key forwarded via the `api-key` header when hitting Qdrant. |

Rate limits (HTTP `429`) are treated as skipped probes so the job reports a neutral result instead of
failing when external providers throttle CI.

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
service. When it encounters a brand-new symbol it automatically seeds the
`instruments` table (using the symbol as the display name) before inserting the
OHLCV rows, so you can bootstrap fresh environments without a separate metadata
seed step.

### Cloud Scheduler trigger

The API exposes `POST /jobs/poll_ohlcv` so Cloud Scheduler can trigger the
ingestion job without shipping the CLI container. Configure the runtime via
environment variables or Secrets Manager:

| Variable | Purpose |
| --- | --- |
| `RAGTRADER_SCHEDULER_COINBASE_SYMBOLS` | Comma-separated Coinbase product IDs. Defaults to `BTC-USD,ETH-USD,SOL-USD`. |
| `RAGTRADER_SCHEDULER_COINBASE_GRANULARITY` | Candle size (aliases like `1m`, `MIN_15`, `3600`). |
| `RAGTRADER_SCHEDULER_COINBASE_LOOKBACK_MINUTES` | Window of history to request per run. Must be positive. |
| `RAGTRADER_SCHEDULER_DATABASE_DSN` / `RAGTRADER_SCHEDULER_DATABASE_SECRET_NAME` | Direct DSN or Secrets Manager name for the ingestion database. Falls back to `RAGTRADER_API_POSTGRES_DSN`. |

1. Provision a service account (e.g. `ragtrader-scheduler`) with Cloud Run
   Invoker + Secret Manager Accessor so it can call the API and read the DSN
   secret.
2. Create the job, targeting your Cloud Run hostname and using the OIDC token
   minted for that service account:

   ```bash
   gcloud scheduler jobs create http ohlcv-poll \
     --schedule="*/5 * * * *" \
     --uri="https://<cloud-run-host>/jobs/poll_ohlcv" \
     --http-method=POST \
     --oidc-service-account-email=ragtrader-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
     --oidc-token-audience="https://<cloud-run-host>" \
     --headers="Content-Type=application/json"
   ```

   Cloud Scheduler supplies the `Authorization: Bearer <token>` header, so the
   endpoint does not require an additional payload.

## Analytics pipeline job (price vs sentiment)

RAGTrader includes a dedicated analytics job that computes lead/lag and price-vs-sentiment metrics and persists them to the analytics tables used by the API.

### What it does

The analytics job:

- Reads OHLCV price data and sentiment z-score time series from Postgres.
- Computes, for each asset and window (e.g., 1h, 4h, 24h):
  - Rolling **Pearson** and **Spearman** correlations between price returns and sentiment z-scores.
- Computes, for each asset pair:
  - Cross-correlation and best lead/lag (FR-7).
  - Granger causality direction and p-values (FR-8).
- Writes results into:
  - `features` (price-vs-sentiment correlation features),
  - `lead_lag` (best lag + strength per pair),
  - `granger_tests` (direction and p-values per pair).

Each instrument symbol receives two feature rows per `(asset, window)` pair: `correlation:return_vs_sentiment:pearson:{window}` and `correlation:return_vs_sentiment:spearman:{window}`. These metrics are computed from aligned price-return and sentiment z-score series. The `/analytics/correlation` API exposes the same data in a sentiment-aware payload:

```json
{
  "status": "ok",
  "metric": "pearson",
  "data": [
    {
      "asset": "BTC-USD",
      "window": "1h",
      "metrics": {
        "pearson": {"value": 0.84, "computed_ts": "2024-01-01T01:00:00+00:00"},
        "spearman": {"value": 0.80, "computed_ts": "2024-01-01T01:00:00+00:00"}
      },
      "value": 0.84,
      "computed_ts": "2024-01-01T01:00:00+00:00"
    }
  ]
}
```

The `value`/`computed_ts` fields mirror whichever metric is configured as the primary (`analytics_correlation_metric`) to preserve backwards compatibility for existing clients.

### Running the analytics job

From the `pipelines/` directory:

```bash
cd pipelines
export DATABASE_URL=postgresql://ragtrader:ragtrader@localhost:5432/ragtrader

PYTHONPATH=src python -m ragtrader_pipelines.analytics_job \
  --start "2024-01-01T00:00:00Z" \
  --end "2024-01-02T00:00:00Z" \
  --window 1h \
  --max-lag-minutes 120
```
