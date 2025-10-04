# Requirements Specifications

### 1. Functional Requirements

#### 1.1 Data Ingestion
- **FR-1:** System shall fetch OHLCV data for at least BTC, ETH, SOL, ADA, BNB, XRP from Coinbase at configurable intervals (default 1–5 min) and store time-aligned series.
- **FR-2:** System shall ingest crypto-related articles/posts from RSS/HTML sources (CoinDesk, CoinTelegraph, Reddit RSS, exchange blogs) at configurable intervals (default 5–10 min), respecting robots.txt and ToS.
- **FR-3:** System shall deduplicate content by URL + normalized title hash + timestamp window.

#### 1.2 NLP & Sentiment
- **FR-4:** System shall classify each item with sentiment polarity (bullish/bearish/neutral) and optional aspects (hype, regulatory, security) and a confidence score.
- **FR-5:** System shall compute rolling sentiment z-scores per coin and window (e.g., 1h, 4h, 24h).

#### 1.3 Analytics
- **FR-6:** System shall compute rolling correlations between price returns and sentiment series.
- **FR-7:** System shall compute cross-correlation and report best lead/lag (minutes/hours) per coin pair and window.
- **FR-8:** System shall run bounded-order Granger causality tests and return p-values and effect directions.
- **FR-9:** System shall build a cross-asset influence graph with edges weighted by recent lead/lag strength or causality evidence.

#### 1.4 Strategy & Backtesting
- **FR-10:** System shall provide a constrained **Strategy DSL v0** with:
  - Conditions: sentiment_zscore(op, value, window), lead_lag(op, value, max_lag, leader, follower)
  - Actions: long | flat; instrument selection.
  - Risk: ATR stop (window, multiplier), position size as fraction of equity.
  - Exits: time limit, take-profit multiple.
- **FR-11:** System shall compile DSL to vectorized execution without arbitrary code execution.
- **FR-12:** System shall output backtest metrics (CAGR, Sharpe, max DD, win rate, turnover) and plots (equity, drawdown, exposure).

#### 1.5 RAG Explorer
- **FR-13:** System shall index item titles + summaries (and optional cleaned body text) into a vector store.
- **FR-14:** System shall answer free-text questions by retrieving top-k items and producing a concise answer with **clickable citations**.

#### 1.6 Web UI
- **FR-15:** Dashboard shall display price & sentiment overlay, lead/lag heatmap, per-pair correlogram, influence graph, and event cards.
- **FR-16:** Strategy Studio shall accept NL description → show parsed DSL → run backtest → display metrics/plots.
- **FR-17:** RAG view shall render query, retrieved snippets (title, source, time), and summary.
- **FR-18:** UI shall show data freshness timestamps and environment badges (DEV/PROD).

#### 1.7 API & Auth
- **FR-19:** Provide REST endpoints for data/analytics and OpenAPI docs.
- **FR-20:** Basic authentication (or Google IAP if available) for non-public endpoints.

#### 1.8 DevEx & CI/CD
- **FR-21:** GitHub Actions shall run lint, type-check, tests, coverage gates, and build Docker images on PRs; main merges trigger deploy to Cloud Run.
- **FR-22:** Pre-commit hooks shall enforce formatters/linters.

### 2. Non-Functional Requirements

#### 2.1 Performance
- **NFR-1:** Typical API responses for analytics ≤ 500 ms with cached data; backtests on 30 days of 1h bars ≤ 3 s.
- **NFR-2:** Dashboard initial paint ≤ 2.5 s on desktop in a clean cache.

#### 2.2 Reliability & Resilience
- **NFR-3:** Ingestion and scraping jobs shall be idempotent with retry and exponential backoff.
- **NFR-4:** System shall tolerate temporary data source outages and continue serving last-known-good data with “stale” badges.

#### 2.3 Security
- **NFR-5:** Secrets stored in Secret Manager; never committed to repo.
- **NFR-6:** Input validation & rate limiting on public endpoints; CORS restricted to known origins.

#### 2.4 Scalability & Portability
- **NFR-7:** Stateless services deployable to Cloud Run; autoscaling enabled; storage layer portable (DuckDB → Postgres/Timescale).
- **NFR-8:** All services packaged as Docker images; environment configured via env vars.

#### 2.5 Maintainability & Testability
- **NFR-9:** Backend test coverage ≥80%; frontend ≥70%; Great Expectations checks for data quality.
- **NFR-10:** Code style: ruff/black/isort/mypy; ESLint/Prettier/TS strict; conventional commits; typed pydantic schemas.

#### 2.6 Observability
- **NFR-11:** Structured JSON logging; request IDs; basic traces/metrics (OpenTelemetry optional); `/healthz` and `/readyz` endpoints.

#### 2.7 Compliance & Ethics
- **NFR-12:** Prominent non-advice disclaimer; robots.txt and ToS respected; source toggles to disable a site if requested; data removal on request for user-submitted content.

### 3. Data Model (MVP)
- **instruments**(symbol, name)
- **ohlcv**(symbol, ts, open, high, low, close, volume, interval)
- **articles**(id, source, url, title, published_ts, fetched_ts, body_excerpt, coins[])
- **sentiments**(article_id, coin, polarity, aspects[], confidence, ts, zscore_window, zscore)
- **features**(symbol, ts, feature_name, value)
- **lead_lag**(leader, follower, window, best_lag_min, strength, computed_ts)
- **granger_tests**(x, y, window, p_value, direction, computed_ts)
- **strategies**(id, name, dsl_yaml, created_ts)
- **backtests**(id, strategy_id, start_ts, end_ts, metrics_json, equity_curve_ref)
- **rag_docs**(doc_id, url, title, published_ts, embedding_ref)

### 4. Acceptance Criteria Summary
- AC-1: Dashboard renders price/sentiment, lead/lag, influence graph with real data.
- AC-2: At least one sample strategy backtest completes with metrics and plots.
- AC-3: RAG query returns a summarized answer with ≥3 citations.
- AC-4: CI pipelines enforce lint, tests, and coverage; Cloud Run deploy succeeds from main.

### 5. Glossary
- **Lead/Lag:** Temporal relationship where one signal precedes another.
- **Granger Causality:** Statistical test for predictive precedence.
- **RAG:** Retrieval-Augmented Generation; LLM answers grounded in retrieved documents.
- **Strategy DSL:** Constrained domain language mapping to vectorized backtests.
