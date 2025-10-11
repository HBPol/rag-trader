# syntax=docker/dockerfile:1.4

FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY api ./api
COPY pipelines ./pipelines

RUN pip install --upgrade pip \
    && pip install ./pipelines ./api

RUN python -c "import ragtrader_api.settings, ragtrader_pipelines.coinbase"

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    API_PORT=8000
WORKDIR /app

RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY api ./api
COPY pipelines ./pipelines

EXPOSE 8000

CMD ["sh", "-c", "uvicorn ragtrader_api.server:app --host 0.0.0.0 --port ${API_PORT}"]
