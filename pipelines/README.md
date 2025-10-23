# RAGTrader Pipelines

This package contains the batch and streaming data jobs that power
RAGTrader. The Coinbase OHLCV ingestion pipeline is joined by the
content sentiment ingestion pipeline, which combines modular source
adapters, a deduplication cache, the shared sentiment classifier, and a
rolling z-score calculator. Both jobs provide scheduler-friendly CLI
entrypoints and registry wiring.

## Analytics dependencies

The analytics stack now leans on the broader scientific Python
ecosystem for graph analytics, statistical modelling, and numerical
helpers. Installing the package will pull in `numpy`, `scipy`,
`statsmodels`, and `networkx`; a lightweight import smoke test in
`tests/test_analytics_dependency_imports.py` asserts that those modules
are importable so contributors spot missing wheels early.

## Development

```bash
pip install -e .[dev]
PYTHONPATH=src pytest --cov=ragtrader_pipelines --cov-report=term --cov-report=xml --cov-fail-under=80
```

Mirroring CI, export `PYTHONPATH=src` so pytest discovers the package modules before applying the
80 percent coverage threshold.

## Coinbase OHLCV ingestion

The [`ragtrader_pipelines.coinbase`](src/ragtrader_pipelines/coinbase.py)
module exposes a reusable job that pulls OHLCV candles from Coinbase and
upserts them into the API service’s `ohlcv` table. Tests in
[`pipelines/tests/test_coinbase_ingestion.py`](../tests/test_coinbase_ingestion.py)
cover the time window selection logic, Coinbase payload transformation,
and the idempotent database writes performed by the repository layer.

Additional registry coverage lives in
[`pipelines/tests/test_registry.py`](../tests/test_registry.py) so future
jobs can follow the same patterns.

### CLI usage

The job ships with a CLI entry point that works locally and in Cloud
Scheduler:

```bash
python -m ragtrader_pipelines.coinbase \
  --symbols BTC-USD,ETH-USD \
  --granularity MIN_60 \
  --lookback-minutes 360 \
  --database-url "postgresql+psycopg://user:pass@localhost:5432/ragtrader"
```

The CLI requires a `DATABASE_URL` (either as a flag or environment
variable) so that results are written to Postgres via SQLAlchemy.
Granularity flags map one-to-one with Coinbase’s candle endpoints.

## Content ingestion & sentiment enrichment

The [`ragtrader_pipelines.content`](src/ragtrader_pipelines/content/__init__.py)
module orchestrates scraping/polling adapters, a Redis-backed dedupe
cache, and the classifier/z-score pipeline. The job can be invoked via
CLI or imported by the scheduler registry. A lightweight
[`__main__` runner](src/ragtrader_pipelines/content/__main__.py) ensures
`python -m ragtrader_pipelines.content` dispatches to the same `main`
function as the registry wiring.

### CLI usage

```bash
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/ragtrader"
export CONTENT_REDDIT_CLIENT_ID=...
export CONTENT_REDDIT_CLIENT_SECRET=...
export CONTENT_COINDESK_API_KEY=...
# export CONTENT_COINDESK_BASE_URL="https://regional.data-api.coindesk.com"  # optional regional host override
python -m ragtrader_pipelines.content \
  --adapters reddit,coindesk \
  --lookback-minutes 180 \
  --freshness-minutes 240 \
  --zscore-window 6
```

Flags mirror the module defaults:

- `--adapters`: Comma-separated adapter slugs (see
  [`content/sources.py`](src/ragtrader_pipelines/content/sources.py)).
- `--lookback-minutes`: Backfill horizon for the adapters.
- `--freshness-minutes`: Guard-rail to skip stale items.
- `--zscore-window`: Rolling window length for the z-score calculator.
- `--source-factory`: Optional dotted path override for advanced setups.

The following environment variables are respected when present:

- `DATABASE_URL`: SQLAlchemy URL for Postgres.
- `CONTENT_COINDESK_API_KEY`: CoinDesk Data API key (legacy
  `CONTENT_RSS_COINDESK_API_KEY` is also honoured).
- `CONTENT_COINDESK_BASE_URL`: Optional CoinDesk Data API host override for
  operators with regional endpoints (aliases `CONTENT_RSS_COINDESK_BASE_URL`).
- `CONTENT_REDDIT_CLIENT_ID` / `CONTENT_REDDIT_CLIENT_SECRET`: Reddit API credentials.
- `CONTENT_DEDUPE_URL`: Redis URL used to persist the dedupe cache.
- `CONTENT_SENTIMENT_MODEL`: Override classifier alias.

### Scheduler guidance

- **Cloud Scheduler / Cloud Run**: mirror the Coinbase job by targeting
  the registry entry point `ragtrader_pipelines.registry:content_ingest`
  and invoking it every 10 minutes. Use a Cloud Run job or service with
  `--freshness-minutes 240` and point `CONTENT_DEDUPE_URL` at a shared
  Redis instance. Retry 3 times with exponential backoff (starting at
  60 seconds) so transient API hiccups are absorbed.
- **Cron (self-hosted)**: run `python -m ragtrader_pipelines.content
  --lookback-minutes 90 --freshness-minutes 180 --zscore-window 6` on a
  15-minute cadence. Keep the Redis-backed dedupe cache reachable so
  concurrent workers can safely share fingerprints.
- **Concurrency**: limit parallel adapters to <=10 to avoid API rate
  limits. When orchestrating via Airflow/Prefect, configure task
  concurrency to 1 per adapter and set retries to 2–3 with jitter.
- **Runtime expectations**: A 90-minute lookback across Reddit + CoinDesk
  Data API content completes in ~2–3 minutes on a 2 vCPU machine. Longer
  backfills scale linearly with the lookback window and adapter count.
