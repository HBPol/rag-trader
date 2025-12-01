"""RAG ingestion job for embedding article summaries into Qdrant."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class ArticleSummary:
    """Serializable view of an article suitable for embedding."""

    id: int
    title: str
    summary: str
    url: str
    source: str
    published_ts: datetime
    coins: Sequence[str] = ()


class ArticleSummaryProvider(Protocol):
    """Return article summaries that have not yet been embedded."""

    def fetch_since(self, since: datetime | None) -> Iterable[ArticleSummary]:
        """Yield article summaries newer than ``since`` (inclusive)."""


class EmbeddingGenerator(Protocol):
    """Generate embeddings for a batch of texts."""

    def embed_batch(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return an embedding vector for each text."""


class FileIngestionState:
    """Persist and retrieve the last ingested timestamp on disk."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> datetime | None:
        if not self._path.exists():
            return None
        raw = json.loads(self._path.read_text())
        value = raw.get("last_ingested")
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def save(self, timestamp: datetime) -> None:
        normalized = timestamp
        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=UTC)
        else:
            normalized = normalized.astimezone(UTC)

        payload = {"last_ingested": normalized.isoformat()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload))


class QdrantIngestionJob:
    """Embed article summaries and upsert them into a Qdrant collection."""

    def __init__(
        self,
        *,
        provider: ArticleSummaryProvider,
        embedder: EmbeddingGenerator,
        qdrant_client: object,
        state: FileIngestionState,
        collection_env_var: str = "QDRANT_COLLECTION",
    ) -> None:
        self._provider = provider
        self._embedder = embedder
        self._qdrant = qdrant_client
        self._state = state
        self._collection_env_var = collection_env_var

    def run(self) -> None:
        collection = os.environ.get(self._collection_env_var)
        if not collection:
            msg = f"Qdrant collection env var '{self._collection_env_var}' is not set"
            raise RuntimeError(msg)

        last_ingested = self._state.load()
        articles = list(self._provider.fetch_since(last_ingested))

        if last_ingested is not None:
            articles = [
                article for article in articles if article.published_ts > last_ingested
            ]

        if not articles:
            return

        texts = [self._embedding_text(article) for article in articles]
        vectors = list(self._embedder.embed_batch(texts))
        if len(vectors) != len(articles):
            raise ValueError("Embedding generator returned mismatched vector count")

        points = [
            {
                "id": article.id,
                "vector": list(vector),
                "payload": {
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "coins": list(article.coins),
                    "published_ts": self._normalize_timestamp(article.published_ts),
                },
            }
            for article, vector in zip(articles, vectors, strict=True)
        ]

        self._qdrant.upsert(collection_name=collection, points=points)

        latest = max(article.published_ts for article in articles)
        self._state.save(latest)

    @staticmethod
    def _normalize_timestamp(value: datetime) -> str:
        if value.tzinfo is None:
            normalized = value.replace(tzinfo=UTC)
        else:
            normalized = value.astimezone(UTC)
        return normalized.isoformat()

    @staticmethod
    def _embedding_text(article: ArticleSummary) -> str:
        summary = article.summary.strip()
        if summary:
            return f"{article.title.strip()}\n\n{summary}"
        return article.title.strip()


__all__ = [
    "ArticleSummary",
    "ArticleSummaryProvider",
    "EmbeddingGenerator",
    "FileIngestionState",
    "QdrantIngestionJob",
]
