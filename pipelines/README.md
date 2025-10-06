# RAGTrader Pipelines

This package contains the batch and streaming data jobs that power
RAGTrader. Subsequent issues will add Coinbase ingestion, news scraping,
and analytics computations. The scaffolding here provides a registry and
quality gates for future work.

## Development

```bash
pip install -e .[dev]
pytest
```

## Coinbase OHLCV ingestion

The `ragtrader_pipelines.coinbase` module exposes a reusable job that
pulls OHLCV candles from Coinbase and upserts them into the API
service’s `ohlcv` table. Tests cover the time window selection logic,
coinbase payload transformation, and the idempotent database writes
performed by the repository layer.

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
