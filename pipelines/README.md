# RAGTrader Pipelines

This package contains the batch and streaming data jobs that power
RAGTrader. The current focus is the Coinbase OHLCV ingestion pipeline,
which is composed of a reusable API client, scheduler-friendly CLI
entrypoints, and a repository layer that writes candles into the
`ragtrader_api` database models. The registry primitives in
`ragtrader_pipelines.registry` hold the job wiring that schedulers import
for execution.

## Development

```bash
pip install -e .[dev]
pytest
```

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
