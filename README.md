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
- Docker Engine + Docker Compose plugin (for the provided stack)
- Copy the root `.env.example` to `.env` so Compose and local tooling share the same configuration

### Bootstrap local environments

```bash
# Create a shared virtual environment for all Python tooling
python -m venv .venv
source .venv/bin/activate

# Install editable packages and root developer requirements
pip install -e api[dev] -e pipelines[dev] -r requirements-dev.txt

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
pnpm test -- --coverage

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
- **Pre-commit** enforces Ruff, Black, isort, mypy, ESLint, and Prettier.
- **Docker Compose & CI** expose the API, web, Postgres, and Redis services (with an optional
  local Qdrant override) described in the [Quickstart](#quickstart), and GitHub Actions already
  runs smoke tests with the stack while we stage deeper pipeline coverage for upcoming CI work.
- **Compose smoke test** ensures `.env.example` and the Docker Compose files stay aligned. Run
  `pytest tests/test_compose.py` before relying on the stack locally or in CI. See [Compose Smoke
  Tests](#compose-smoke-tests) for details on the scenarios covered.
- **External reachability probes** live in [`tools/reachability.py`](tools/reachability.py). They
  verify Coinbase, RSS feeds, and Qdrant respond before we run heavier jobs. Execute
  `python tools/reachability.py` locally or rely on the "External Reachability" CI job to exercise
  them on every push.
- **PyCharm + Docker**: add a Docker Compose interpreter pointed at the `api` service so
  editor actions reuse the container runtime. In *Settings → Project → Python Interpreter*,
  click **Add Interpreter… → Docker Compose**, select `docker-compose.yml` (and optionally
  `docker-compose.override.yml` if you want the extra services), choose the **Service** named
  `api`, and keep the default `/usr/local/bin/python` path that PyCharm shows. That binary is the
  interpreter baked into the image that ships with the project, so linting, tests, and run
  configurations inside PyCharm mirror what `docker compose up` executes.

#### Run pre-commit locally

The root [`.pre-commit-config.yaml`](.pre-commit-config.yaml) defines the exact linting and
formatting jobs that GitHub Actions executes. Python-focused hooks (Ruff, Black, isort, mypy)
target the `api/` and `pipelines/` packages, while the JavaScript/TypeScript hooks (ESLint and
Prettier) cover the `web/` app. Run everything from the repository root before opening a PR—there's
no need to `cd` into individual packages, because `pre-commit run --all-files` mirrors the CI
workflow one-for-one:

```bash
pre-commit install      # sets up the Git hook using the shared virtualenv
pre-commit run --all-files
```

All hooks now execute in the shared virtualenv described in [Bootstrap local environments](#bootstrap-local-environments)
(for example: `pip install -e api[dev] -e pipelines[dev] ...`). Activate that environment before
running `pre-commit run` so the Python tooling and dependencies are available without
package-specific bootstrapping.

Mypy mirrors the GitHub Actions matrix: execute it once from `api/` and once from
`pipelines/` so the service-specific `pyproject.toml` configs load in strict mode.
`pre-commit run mypy --all-files` wraps those two invocations, matching CI exactly:

```bash
cd api && mypy --config-file=pyproject.toml
cd pipelines && mypy --config-file=pyproject.toml
pre-commit run mypy --all-files
```

To re-run a specific hook against the full tree, use the hook's name explicitly. Each hook below is
available via `pre-commit run <hook> --all-files`:

```bash
pre-commit run ruff --all-files      # Python linting & formatting (Ruff)
pre-commit run black --all-files     # Python formatting (Black)
pre-commit run isort --all-files     # Python import sorting (isort)
pre-commit run mypy --all-files      # Python type checks (api/ and pipelines/)
pre-commit run eslint --all-files    # Web linting (ESLint)
pre-commit run prettier --all-files  # Web formatting (Prettier)
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

The coverage invocations match the CI gates (80% minimum for Python packages and full Vitest
coverage reports for the frontend). Run them after `pip install -e .[dev]` (Python) or `pnpm install`
(web) so local tooling mirrors GitHub Actions.

## Quickstart

```bash
# Set up env
cp .env.example .env

# Fill in vector store credentials from Qdrant Cloud so the API can reach your cluster
$EDITOR .env  # set QDRANT_URL and QDRANT_API_KEY to match .env.example hints

# Validate Compose parity and health checks
pytest tests/test_compose.py

# Run with remote Qdrant (Cloud)
docker compose up -d --build

# OR run fully offline (disables the vector store requirement until you bring one online)
RAGTRADER_API_REQUIRE_VECTOR_STORE=false docker compose up -d --build

# OR run with local Qdrant (override adds qdrant service + points API to it)
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build

# health checks
curl -f http://localhost:8000/healthz
open http://localhost:5173
```

> **Notes**
> - You can create or reuse a managed cluster in [Qdrant Cloud](https://qdrant.tech/cloud/) to obtain the `QDRANT_URL` and `QDRANT_API_KEY` values referenced in `.env.example`.
> - The override stack is opt-in: include `-f docker-compose.override.yml` when you want the co-located Qdrant container, or omit it to keep pointing at Qdrant Cloud.

Once the services report healthy, exercise the FastAPI service at
`http://localhost:8000/docs` or `http://localhost:8000/healthz` and browse the web frontend on
`http://localhost:5173` to confirm the containers are wired together correctly.

### Docker Compose profiles

The repository ships two Compose descriptors:

- `docker-compose.yml` is the baseline stack used in CI smoke tests. It provisions the API,
  frontend, and supporting services that are shared across environments (e.g. Postgres, Redis).
- `docker-compose.override.yml` is opt-in. It swaps the API from using the managed Qdrant Cloud
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
with [`docker-compose.override.yml`](docker-compose.override.yml)) and assert each service's
`/healthz` endpoint responds successfully.

## External reachability probes

[`tools/reachability.py`](tools/reachability.py) provides lightweight HTTP checks for Coinbase,
required RSS feeds, and Qdrant. The script powers the "External Reachability" GitHub Actions job and
can be run manually via:

```bash
python tools/reachability.py
```

The following environment variables control its behaviour (see [`.env.example`](.env.example) for
defaults):

| Variable | Purpose |
| --- | --- |
| `REACHABILITY_SKIP_ALL` | Skip every probe (useful when running CI in a fully offline environment). |
| `REACHABILITY_SKIP_COINBASE` | Skip the Coinbase probe while keeping RSS/Qdrant. |
| `REACHABILITY_SKIP_RSS` | Skip RSS feed checks. |
| `REACHABILITY_SKIP_QDRANT` | Skip the Qdrant health check. |
| `REACHABILITY_RSS_FEEDS` | Comma-separated list of RSS feed URLs to probe. |
| `REACHABILITY_QDRANT_URL` | Overrides `QDRANT_URL` for the Qdrant health check, if needed. |
| `REACHABILITY_TIMEOUT_SECONDS` | HTTP timeout applied to each request (defaults to 10 seconds). |
| `RSS_BASIC_AUTH` | `username:password` pair for RSS feeds that require HTTP Basic authentication. |
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
service.
