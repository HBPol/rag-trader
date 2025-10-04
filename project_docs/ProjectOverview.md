# Project Plan

### Name & Tagline
**RAGTrader** — *Retrieve. Reason. Trade.*

### Elevator Pitch
RAGTrader is a crypto analytics and prototyping platform that fuses price data from Coinbase with crowd/news sentiment gathered via scrapers and RSS. In a live, interactive dashboard, users see how sentiment leads or lags price across coins, explore causal relationships, and spin up backtestable strategies using a safe strategy DSL. A lightweight RAG explorer answers "why did this move happen?" with cited snippets.

### Target Users
- **Discretionary crypto traders** who want quick, visual conviction from sentiment vs price.
- **Quant-curious engineers** needing a sandbox to test lead/lag and sentiment-based ideas fast.
- **Consulting prospects** evaluating ability to ship ML/NLP + quant MVPs under tight timelines.

### MVP Goals (7–10 days)
- Ingest OHLCV for top coins from Coinbase.
- Scrape/RSS ingest recent crypto news & forum content.
- Classify sentiment + compute rolling z-scores.
- Visualize price vs sentiment; compute rolling correlations & lead/lag cross-correlations.
- Show cross-asset effects (influence graph) and report simple Granger causality tests.
- Prototype a **Strategy DSL** + vectorized backtester; run at least one sentiment/lead-lag strategy.
- RAG Explorer v0: retrieve relevant snippets and summarize with citations.

### Non-Goals (MVP)
- Live trading or exchange account linking.
- Complex execution simulation (basic slippage model only).
- Proprietary paid data sources.

### Data Sources
- **Prices:** Coinbase REST API (OHLCV).
- **Sentiment content (no/low-API):** CoinDesk/ CoinTelegraph RSS, Reddit RSS (r/CryptoCurrency, r/Bitcoin, r/ethfinance), exchange blogs, selected forums where ToS allows. Respect robots.txt and rate limits.

### Core Features
1. **Dashboard**
   - Overlay price & sentiment (z-score) with selectable windows (1h/4h/24h/7d).
   - Lead/lag cross-correlogram & best-lag indicator per coin pair.
   - Cross-asset **Influence Graph** (edge weight = causality/lead strength).
   - Event Cards from headlines with time, source, sentiment, and likely impacted coins.
2. **Strategy Studio**
   - Natural-language → **Strategy DSL** via LLM with guardrails.
   - Vectorized backtests; metrics (CAGR, Sharpe, max DD, hit rate, turnover).
3. **RAG Explorer**
   - Ask questions; retrieve snippets; concise LLM summary with citations.

### Architecture Overview
- **Frontend:** Next.js (TS), Tailwind + shadcn/ui, Plotly/Recharts, TanStack Query.
- **Backend:** FastAPI (Python). Services: ingestion (prices, articles), NLP pipeline (sentiment), analytics (lead/lag, Granger), backtester, RAG.
- **Storage:** DuckDB + Parquet (fast MVP) or Postgres/Timescale. Vector store: Qdrant/Chroma.
- **Infra:** Docker; Cloud Run services; Cloud Scheduler for jobs; Secret Manager.

### Demo Narrative (Portfolio)
1. Select BTC & ETH → dashboard highlights a 60–90m sentiment lead over last 24h.
2. Click an Event Card → RAG Explorer shows snippets (CoinDesk/Reddit) and a 2-sentence LLM rationale.
3. In Strategy Studio, type: *“Long ETH when BTC sentiment z-score > 1 and BTC leads ETH under 2h; ATR stop 2x.”* → DSL renders → backtest shows equity curve & stats.

### Risks & Mitigations
- **Scraper fragility:** Prefer RSS; modular adapters; caching; source toggles in UI.
- **LLM latency/cost:** Cache, batch, allow local/zero-shot fallback.
- **Look-ahead bias:** Strict timestamping; unit tests to prevent leakage; walk-forward where feasible.
- **Overfitting:** Out-of-sample splits; report both IS/OOS; keep parameters few.

### Compliance & Ethics
- Prominent **“Educational use only — not financial advice.”**
- Respect site ToS/robots; provide per-source enable/disable.
- Clearly display data freshness timestamps.
