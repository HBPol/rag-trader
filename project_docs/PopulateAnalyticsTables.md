# Populating analytics tables with live data

Use this walk-through when you already have real market data in `ohlcv`, `articles`, and `sentiments` and want to backfill the analytics tables (`features`, `lead_lag`, and `granger_tests`).

## 1. Environment setup

```bash
cd /workspace/rag-trader
python -m venv .venv
source .venv/bin/activate
pip install -e api -e pipelines

export RAGTRADER_API_POSTGRES_DSN="postgresql+psycopg://user:pass@localhost:5432/ragtrader"
```

Replace the DSN with the credentials for the database that already contains your ingested market data.

## 2. Make sure migrations are up to date

```bash
python - <<'PY'
import os
from ragtrader_api.settings import ApiSettings
from ragtrader_api.db.database import create_engine
from ragtrader_api.db.migrations import apply_migrations

dsn = os.environ["RAGTRADER_API_POSTGRES_DSN"]
settings = ApiSettings(postgres_dsn=dsn, require_database=True, require_vector_store=False)
engine = create_engine(settings)
apply_migrations(engine)
print("Migrations applied")
PY
```

This upgrades the schema to the latest Alembic revision so the analytics tables exist before you backfill them.

## 3. Compute analytics from live candles

The script below loads hourly Coinbase candles for BTC and ETH. Update the `SYMBOLS` list so it matches the instrument codes that actually appear in your `ohlcv` table (for example some older datasets might use bare `BTC` / `ETH` symbols rather than `BTC-USD` / `ETH-USD`). If you are unsure which codes exist, run `SELECT DISTINCT symbol FROM ohlcv ORDER BY 1;` against your database first. The SQL still filters by the `interval` label `MIN_60`, but you can switch that to any cadence you maintain.

```bash
python - <<'PY'
import os
from datetime import UTC
from decimal import Decimal

import pandas as pd

from ragtrader_api.settings import ApiSettings
from ragtrader_api.db.database import create_engine, session_factory
from ragtrader_api.db.repositories.analytics import (
    FeatureRecord,
    LeadLagRecord,
    GrangerTestRecord,
    SqlAlchemyAnalyticsRepository,
)
from ragtrader_pipelines.analytics.cross_correlation import best_cross_correlation
from ragtrader_pipelines.analytics.granger import run_granger_causality

SYMBOLS = ["BTC-USD", "ETH-USD"]
INTERVAL = "MIN_60"

dsn = os.environ["RAGTRADER_API_POSTGRES_DSN"]
settings = ApiSettings(postgres_dsn=dsn, require_database=True, require_vector_store=False)
engine = create_engine(settings)
SessionFactory = session_factory(engine)
repo = SqlAlchemyAnalyticsRepository(SessionFactory)

with engine.connect() as conn:
    candles = pd.read_sql(
        """
        SELECT ts, symbol, close
        FROM ohlcv
        WHERE symbol = ANY(%(symbols)s) AND interval = %(interval)s
        ORDER BY ts
        """,
        conn,
        params={"symbols": SYMBOLS, "interval": INTERVAL},
        parse_dates=["ts"],
    )

wide = candles.pivot(index="ts", columns="symbol", values="close").dropna()
missing = [symbol for symbol in SYMBOLS if symbol not in wide.columns]
if missing:
    raise SystemExit(
        "Symbols not found in OHLCV data: "
        + ", ".join(missing)
        + f". Available columns: {', '.join(wide.columns)}"
    )
returns = wide.pct_change().dropna()

feature_records = [
    FeatureRecord(
        symbol=symbol,
        feature_name="return_1h",
        ts=ts.to_pydatetime().replace(tzinfo=UTC),
        value=Decimal(str(value)),
    )
    for symbol, series in returns.items()
    for ts, value in series.items()
]
repo.upsert_features(feature_records)

leader_symbol, follower_symbol = SYMBOLS
lag_result = best_cross_correlation(wide[leader_symbol], wide[follower_symbol], max_lag=6)
if lag_result:
    lag_steps, score = lag_result
    repo.upsert_lead_lag(
        [
            LeadLagRecord(
                leader=leader_symbol,
                follower=follower_symbol,
                window="1h",
                best_lag_min=lag_steps * 60,
                strength=Decimal(str(score)),
                computed_ts=returns.index[-1].to_pydatetime().replace(tzinfo=UTC),
            )
        ]
    )

summary = run_granger_causality(
    wide[leader_symbol], wide[follower_symbol], max_lag=6, significance=0.05
)
repo.upsert_granger_tests(
    [
        GrangerTestRecord(
            x_symbol=leader_symbol,
            y_symbol=follower_symbol,
            window="1h",
            p_value=Decimal(str(summary.leader_to_follower.p_value)),
            direction="x->y",
            computed_ts=returns.index[-1].to_pydatetime().replace(tzinfo=UTC),
        ),
        GrangerTestRecord(
            x_symbol=follower_symbol,
            y_symbol=leader_symbol,
            window="1h",
            p_value=Decimal(str(summary.follower_to_leader.p_value)),
            direction="x->y",
            computed_ts=returns.index[-1].to_pydatetime().replace(tzinfo=UTC),
        ),
    ]
)

print(f"Inserted {len(feature_records)} features")
PY
```

Running the script is idempotent: re-computing the same keys simply refreshes the stored values.

## 4. Spot-check the backfill

```bash
python - <<'PY'
import os
from ragtrader_api.settings import ApiSettings
from ragtrader_api.db.database import create_engine
from ragtrader_api.db.repositories.analytics import SqlAlchemyAnalyticsRepository, sessionmaker

dsn = os.environ["RAGTRADER_API_POSTGRES_DSN"]
settings = ApiSettings(postgres_dsn=dsn, require_database=True, require_vector_store=False)
engine = create_engine(settings)
SessionFactory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
repo = SqlAlchemyAnalyticsRepository(SessionFactory)

print(repo.list_features(symbol="BTC-USD", feature_name="return_1h", limit=5))
print(repo.list_lead_lag(leader="BTC-USD", follower="ETH-USD", window="1h"))
print(repo.list_granger_tests(x_symbol="BTC-USD", y_symbol="ETH-USD", window="1h"))
PY
```

Use these helpers as a template for your own batch jobs—swap in different symbols, feature engineering logic, or statistical windows to populate the analytics tables with the metrics you need.
