# Project Plan

### Timeline (10 calendar days; ~5 issues ≈ 2 workdays each)
- **Days 1–2 — Issue #1:** Repo scaffold, CI/CD baseline, price ingestion.
- **Days 3–4 — Issue #2:** Content ingestion & sentiment pipeline.
- **Days 5–6 — Issue #3:** Analytics (lead/lag, correlation, Granger) + API.
- **Days 7–8 — Issue #4:** Web dashboard (charts, heatmap, influence graph).
- **Days 9–10 — Issue #5:** Strategy DSL + backtester; RAG Explorer v0; Cloud Run deploy.

> Each issue includes tests, docs, and demo data. Coverage target ≥80% backend; ≥70% frontend.

---

### Issue #1 — Foundation & Price Ingestion
**Goal:** Solid repo/infra with automated quality gates; Coinbase OHLCV ingest to storage.

**Tasks**
- **Monorepo** scaffold (`/web`, `/api`, `/pipelines`) with **GitFlow** branching (main, develop, feature/*, hotfix/*).
- GitHub Actions: lint, type-check, tests, coverage gates, Docker build.
- Python: FastAPI skeleton; **Postgres (Timescale optional) as a docker service** for time‑series/metadata (no files in repo); Coinbase OHLCV poller.
- Frontend: Next.js skeleton, UI kit setup (shadcn/ui), auth gate (basic).
- Pre-commit: ruff, black, isort, mypy; ESLint, Prettier, TypeScript strict.
- Vector store wired to **Qdrant Cloud (Free Tier)** (or self‑hosted Qdrant as a docker service for offline dev). Add thin repository interface to allow swapping providers.
- **Dev/Prod parity**: compose files align with Cloud Run deploys; development secrets via `.env`.
- CI smoke **reachability tests** for Coinbase, RSS endpoints, and Qdrant (with graceful skip on rate limits).


**Deliverables**
- Passing CI on PRs; Docker images build.
- CLI/job to fetch top 6–10 coins OHLCV into `data/` or bucket.
- Basic health endpoint & docs.

**Acceptance Criteria**
- `make test` passes with ≥80% backend coverage.
- Scheduled job (local + Cloud Scheduler) writes fresh OHLCV.
- CI logs show successful external **reachability** checks (Coinbase/RSS/Qdrant) in the pipeline.

---

### Issue #2 — Content Ingestion & Sentiment
**Goal:** Gather news/forum items; compute sentiment & z-scores.

**Tasks**
- RSS/HTML adapters (CoinDesk, CoinTelegraph, Reddit RSS). Caching + dedupe.
- Text cleaning, language detection, timestamp normalization.
- Sentiment classifier: zero/weak-shot (rule-based + small model) with confidence; multi-label: bullish/bearish, hype, regulatory, security.
- Rolling z-score computation per coin & window.

**Deliverables**
- `articles` and `sentiments` tables populated for last 3–7 days.
- Unit tests for parsing and classifier consistency.

**Acceptance Criteria**
- Endpoints: `GET /sentiment?symbol=BTC&window=1h` returns series with timestamps; freshness < 10 min behind ingestion.

---

### Issue #3 — Analytics Engine & API
**Goal:** Lead/lag, correlations, and Granger tests exposed via API.

**Tasks**
- Rolling Pearson/Spearman correlation utilities.
- Cross-correlation function (CCF) to find best lag.
- Granger causality (statsmodels) with guardrails.
- Influence graph builder (edge weights, thresholds).

**Deliverables**
- Endpoints: `/analytics/leadlag`, `/analytics/correlation`, `/analytics/granger`, `/analytics/influence-graph`.
- Data tests (Great Expectations) for NaNs, gaps, time alignment.

**Acceptance Criteria**
- Given seeded demo data, endpoints return plausible values and are reproducible in tests.

---

### Issue #4 — Web UI Dashboard
**Goal:** Flashy, responsive UI that’s actually useful.

**Tasks**
- Price + sentiment overlay chart with window controls.
- Lead/lag heatmap (matrix across coin pairs) & per-pair correlogram.
- Influence graph (force-directed) with tooltips & edge strength legend.
- Event Cards linking to source URLs.
- **Causality Map**: animated network where edges **pulse** in real time as relationships strengthen/weakening.
- **Explainability chips**: hover any metric/label to see a one‑sentence LLM explanation with a source link.

**Deliverables**
- `/dashboard` route with the above widgets.
- Playwright smoke tests; Lighthouse performance ≥85 on desktop.

**Acceptance Criteria**
- User can select BTC/ETH and see lead/lag + best-lag label update under 1s after API response.
- **Explainability chips** appear on hover with a one‑sentence rationale and a live source link.
- **Causality Map** edges visibly pulse in response to changing edge strengths.

---

### Issue #5 — Strategy Studio + RAG v0 + Deploy
**Goal:** Prototype strategy definition + backtest; minimal RAG Explorer; deploy on Cloud Run.

**Tasks**
- **Strategy DSL v0:** conditions (sentiment z-score, lead/lag threshold), actions (long/flat), ATR stop, size fraction.
- Vectorized backtester with basic slippage & fee assumptions.
- LLM prompt → DSL converter with JSON schema validation (no eval).
- RAG: ingest titles + summaries to vector store; question → retrieve top-k → concise answer with citations.
- Finalize **vector store** per **ADR-001** (Qdrant vs Chroma); default to Qdrant Cloud.
- Cloud Run deploys (web/api), Cloud Scheduler for jobs, basic auth + secrets.

**Deliverables**
- `/studio` route to define strategy, run backtest, show equity & stats.
- `/rag` route with query box, retrieved snippets, and summary.
- Production URLs; deployment docs.

**Acceptance Criteria**
- Demo strategy backtest runs < 3s on 30 days of 1h bars.
- RAG answers a “why” query with ≥3 citations and returns < 2s after retrieval.

---

### Final Deliverables (MVP)
- Deployed **RAGTrader** (web + API) on Cloud Run with demo data and basic auth.
- Interactive dashboard (price/sentiment overlay, lead/lag, influence graph, event cards).
- Strategy Studio with DSL v0 and backtester + at least one example strategy.
- RAG Explorer v0 with citations.
- CI/CD pipelines (linting, tests, coverage gates, Docker build/push, deploy).
- Technical docs: README, the three project docs, API reference (OpenAPI), and runbooks.

---
