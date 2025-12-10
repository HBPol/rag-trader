"""Integration-style tests for the RAG ingestion job."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

import pytest

from ragtrader_pipelines.rag.ingest import (
    ArticleSummary,
    EmbeddingGenerator,
    FileIngestionState,
    QdrantIngestionJob,
)


class _StubProvider:
    def __init__(self, articles: Sequence[ArticleSummary]) -> None:
        self._articles = list(articles)
        self.requested_since: datetime | None = None

    def fetch_since(self, since: datetime | None) -> Iterable[ArticleSummary]:
        self.requested_since = since
        return list(self._articles)


class _StubEmbedder(EmbeddingGenerator):
    def __init__(self) -> None:
        self.captured_texts: list[str] = []

    def embed_batch(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.captured_texts = list(texts)
        return [[float(idx), float(idx + 1)] for idx in range(len(texts))]


class _StubQdrant:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[dict[str, object]]]] = []

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]) -> None:
        self.upserts.append((collection_name, points))


@pytest.fixture()
def article_batch() -> list[ArticleSummary]:
    return [
        ArticleSummary(
            id=1,
            title="BTC rally continues",
            summary="Bitcoin climbs on ETF inflows",
            url="https://example.com/btc",
            source="coindesk",
            published_ts=datetime(2024, 5, 10, 12, 0, tzinfo=UTC),
            coins=["BTC"],
        ),
        ArticleSummary(
            id=2,
            title="ETH developers eye upgrade",
            summary="Shanghai follow-up gains momentum",
            url="https://example.com/eth",
            source="cointelegraph",
            published_ts=datetime(2024, 5, 11, 8, 30, tzinfo=UTC),
            coins=["ETH"],
        ),
    ]


def test_upserts_articles_with_expected_payload(monkeypatch, tmp_path, article_batch):
    monkeypatch.setenv("QDRANT_COLLECTION", "articles-test")
    provider = _StubProvider(article_batch)
    embedder = _StubEmbedder()
    client = _StubQdrant()
    state = FileIngestionState(tmp_path / "state.json")

    job = QdrantIngestionJob(
        provider=provider,
        embedder=embedder,
        qdrant_client=client,
        state=state,
    )

    job.run()

    assert provider.requested_since is None
    assert len(client.upserts) == 1
    collection, points = client.upserts[0]
    assert collection == "articles-test"

    assert embedder.captured_texts == [
        "BTC rally continues\n\nBitcoin climbs on ETF inflows",
        "ETH developers eye upgrade\n\nShanghai follow-up gains momentum",
    ]

    assert points[0]["id"] == 1
    assert points[0]["payload"]["source"] == "coindesk"
    assert points[0]["payload"]["published_ts"] == "2024-05-10T12:00:00+00:00"
    assert points[0]["payload"]["coins"] == ["BTC"]
    assert state.load() == article_batch[-1].published_ts


def test_ingestion_is_idempotent(monkeypatch, tmp_path, article_batch):
    monkeypatch.setenv("QDRANT_COLLECTION", "articles-test")
    provider = _StubProvider(article_batch)
    embedder = _StubEmbedder()
    client = _StubQdrant()
    state = FileIngestionState(tmp_path / "state.json")

    job = QdrantIngestionJob(
        provider=provider,
        embedder=embedder,
        qdrant_client=client,
        state=state,
    )

    job.run()
    first_ingested = state.load()

    job.run()

    assert provider.requested_since == first_ingested
    assert len(client.upserts) == 1
    assert state.load() == first_ingested


def test_missing_collection_env_var_raises(monkeypatch, tmp_path, article_batch):
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    provider = _StubProvider(article_batch)
    embedder = _StubEmbedder()
    client = _StubQdrant()
    state = FileIngestionState(tmp_path / "state.json")

    job = QdrantIngestionJob(
        provider=provider,
        embedder=embedder,
        qdrant_client=client,
        state=state,
    )

    with pytest.raises(RuntimeError, match="collection env var 'QDRANT_COLLECTION'"):
        job.run()


def test_mismatched_embedding_counts_raise(monkeypatch, tmp_path, article_batch):
    monkeypatch.setenv("QDRANT_COLLECTION", "articles-test")
    provider = _StubProvider(article_batch)

    class _BadEmbedder(_StubEmbedder):
        def embed_batch(self, texts: Sequence[str]):
            super().embed_batch(texts)
            return [[0.0, 1.0]]  # not enough vectors

    client = _StubQdrant()
    state = FileIngestionState(tmp_path / "state.json")

    job = QdrantIngestionJob(
        provider=provider,
        embedder=_BadEmbedder(),
        qdrant_client=client,
        state=state,
    )

    with pytest.raises(ValueError, match="mismatched vector count"):
        job.run()
