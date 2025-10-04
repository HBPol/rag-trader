# Project Overview

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
 

**Portfolio polish (UI)**
- **Causality Map**: animated network where edges **pulse** in real time as relationships strengthen/weakening.
- **Explainability chips**: hover any metric to see a one‑sentence LLM explanation with a source link.
  - Ask questions; retrieve snippets; concise LLM summary with citations.

### Architecture Overview
- **Frontend:** Next.js (TS), Tailwind + shadcn/ui, Plotly/Recharts, TanStack Query.
- **Backend:** FastAPI (Python). Services: ingestion (prices, articles), NLP pipeline (sentiment), analytics (lead/lag, Granger), backtester, RAG.
- **Storage:** **Postgres (Timescale optional) as a docker service** for time‑series & metadata (no files inside the repo). **Vector store:** **Qdrant Cloud (Free Tier)** by default; Chroma supported behind an abstraction if required.
- **Infra:** Docker with **immutable containers**; **12‑Factor** alignment; Cloud Run services; Cloud Scheduler for jobs; Secret Manager (prod) and `.env` files (dev).

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


### Engineering Workflow
- **Monorepo** layout (`/web`, `/api`, `/pipelines`).
- **GitFlow** branching: `main`, `develop`, feature branches (`feature/*`), and `hotfix/*` when needed.
- CI runs lint, type checks, tests, coverage gates, Docker build, and **external reachability smoke tests** (Coinbase/RSS/Qdrant).
- Dev/Prod parity: compose files mirror production; secrets in dev via `.env`.

### Runbook: Dev vs Prod

**Prereqs**  
- Docker & Docker Compose, Node 20+, Python 3.11.  
- (Prod) `gcloud` CLI authenticated to your project.  
- Qdrant Cloud API key (free tier) or self-hosted Qdrant service in compose.

**Environment files**  
Create `.env` files (no secrets committed):
```bash
# .env (shared defaults for compose)
ENV=dev
POSTGRES_HOST=postgres
POSTGRES_DB=ragtrader
POSTGRES_USER=ragtrader
POSTGRES_PASSWORD=ragtrader
API_PORT=8000
WEB_PORT=5173
QDRANT_URL=https://<your-qdrant-endpoint>
QDRANT_API_KEY=<your-key>
COINBASE_API_BASE=https://api.exchange.coinbase.com
```

**Local Dev** (parity with prod where possible)
```bash
# start everything
docker compose up -d --build
# view logs
docker compose logs -f api
# health checks
curl -f http://localhost:${API_PORT:-8000}/healthz
open http://localhost:${WEB_PORT:-5173}
# run tests (incl. external reachability smoke tests)
docker compose exec api pytest -q
```

To use **self-hosted Qdrant** in dev, add the `qdrant` service to `docker-compose.yml` and set `QDRANT_URL=http://qdrant:6333`.

**Production (Cloud Run example)**  
Build images with immutable tags (git SHA), push, and deploy:
```bash
export PROJECT_ID=<gcp-project>
export REGION=europe-west1
export TAG=$(git rev-parse --short HEAD)

# build & push
docker build -t gcr.io/$PROJECT_ID/ragtrader-api:$TAG -f api/Dockerfile .
docker build -t gcr.io/$PROJECT_ID/ragtrader-web:$TAG -f web/Dockerfile .
docker push gcr.io/$PROJECT_ID/ragtrader-api:$TAG
docker push gcr.io/$PROJECT_ID/ragtrader-web:$TAG

# secrets (one-time)
# gcloud secrets create QDRANT_API_KEY --data-file=-  (or use Console)
# gcloud secrets create DATABASE_URL --data-file=-

# deploy
gcloud run deploy ragtrader-api   --image gcr.io/$PROJECT_ID/ragtrader-api:$TAG   --region $REGION   --set-env-vars=ENV=prod,QDRANT_URL=<cloud-endpoint>,COINBASE_API_BASE=https://api.exchange.coinbase.com   --set-secrets=QDRANT_API_KEY=QDRANT_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest

gcloud run deploy ragtrader-web   --image gcr.io/$PROJECT_ID/ragtrader-web:$TAG   --region $REGION   --set-env-vars=ENV=prod,API_BASE_URL=<api-url>

# (optional) scheduler for polling
gcloud scheduler jobs create http ohlcv-pull   --schedule="*/5 * * * *"   --uri="<api-url>/jobs/poll_ohlcv"   --http-method=POST   --oauth-service-account-email=<svc>@$PROJECT_ID.iam.gserviceaccount.com
```

**Rollback**
```bash
gcloud run revisions list --service=ragtrader-api --region $REGION
gcloud run services update-traffic ragtrader-api --region $REGION --to-revisions <prev>=100
```

**Observability**  
- Local: `docker compose logs -f` for `api`, `web`, `postgres`.  
- Prod: Cloud Run logs & metrics; add uptime checks for `/healthz`.
