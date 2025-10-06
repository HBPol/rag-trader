FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "ragtrader_api.server:app", "--host", "0.0.0.0", "--port", "8000"]
