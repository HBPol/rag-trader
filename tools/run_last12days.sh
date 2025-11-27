#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Window: Last 12 days
# -----------------------------
LOOKBACK_DAYS=12
LOOKBACK_MINUTES=$((LOOKBACK_DAYS * 24 * 60))

# Compute UTC start/end
START=$(date -u -d "${LOOKBACK_DAYS} days ago" +"%Y-%m-%dT%H:%M:%SZ")
END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "========================================"
echo "RAGTrader: Last ${LOOKBACK_DAYS} days window"
echo "Start: $START"
echo "End:   $END"
echo "Lookback (minutes): $LOOKBACK_MINUTES"
echo "========================================"

# -----------------------------
# 1. CONTENT INGESTION + SENTIMENT
# -----------------------------
echo "[1/3] Running content ingestion..."
python -m ragtrader_pipelines.content \
  --adapters coindesk \
  --lookback-minutes "${LOOKBACK_MINUTES}" \
  --freshness-minutes 480 \
  --zscore-window 6


# -----------------------------
# 2. OHLCV INGESTION (Coinbase)
# -----------------------------
echo "[2/3] Fetching OHLCV data (1h bars)..."
python -m ragtrader_pipelines.coinbase \
  --symbols ADA,ARB,BTC,DOGE,ETH,MATIC,SOL,USDT,XRP \
  --granularity MIN_60 \
  --lookback-minutes "${LOOKBACK_MINUTES}" \
  --quote-currency USD \
  --database-url "$DATABASE_URL"


# -----------------------------
# 3. ANALYTICS JOB
# -----------------------------
echo "[3/3] Running analytics job (FR-6 to FR-9)..."
python -m ragtrader_pipelines.analytics_job \
  --start "$START" \
  --end "$END" \
  --symbols ADA,ARB,BTC,DOGE,ETH,MATIC,SOL,USDT,XRP \
  --windows 1h,4h \
  --price-interval 1h \
  --sentiment-window 6 \
  --max-lag-minutes 60 \
  --database-url "$DATABASE_URL"

echo "========================================"
echo "Done! All pipelines executed successfully."
echo "========================================"
