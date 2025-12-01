from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from ragtrader_api.routes.rag import RagSnippet, create_rag_app


@dataclass
class _FakePoint:
    id: str
    payload: dict
    score: float


class _FakeQdrant:
    def __init__(self, points: list[_FakePoint]):
        self._points = points
        self.calls: list[dict[str, object]] = []

    def search(self, **kwargs):  # type: ignore[override]
        self.calls.append(kwargs)
        return self._points


class _Summarizer:
    def __init__(self, summary: str):
        self.summary = summary
        self.calls: list[dict[str, object]] = []

    def summarize(self, *, query: str, snippets: list[RagSnippet]) -> str:
        self.calls.append({"query": query, "snippets": snippets})
        return self.summary


def _points() -> list[_FakePoint]:
    return [
        _FakePoint(
            id="a1",
            payload={
                "title": "Alpha update",
                "source": "unit-test",
                "published_at": "2024-02-01T00:00:00Z",
                "content": "Alpha content",
            },
            score=0.9,
        ),
        _FakePoint(
            id="b2",
            payload={
                "title": "Beta news",
                "source": "unit-test",
                "published_at": "2024-02-02T00:00:00Z",
                "content": "Beta content",
            },
            score=0.85,
        ),
    ]


def test_rag_route_returns_snippets_and_summary() -> None:
    summarizer = _Summarizer("Alpha [1]; Beta [2]")
    qdrant = _FakeQdrant(_points())
    app = create_rag_app(client=qdrant, summarizer=summarizer)
    client = TestClient(app)

    response = client.post("/rag", json={"query": "crypto momentum"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "crypto momentum"
    assert payload["summary"] == "Alpha [1]; Beta [2]"
    assert len(payload["snippets"]) == 2
    assert payload["snippets"][0]["title"] == "Alpha update"
    assert qdrant.calls[-1]["collection_name"] == "rag-cluster"
    assert qdrant.calls[-1]["limit"] == 5


def test_default_summary_formats_citations() -> None:
    qdrant = _FakeQdrant(_points())
    app = create_rag_app(client=qdrant)
    client = TestClient(app)

    response = client.post("/rag", json={"query": "market structure"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["snippets"][0]["citation"] == 1
    assert payload["snippets"][1]["citation"] == 2
    assert "[1]" in payload["summary"]
    assert "[2]" in payload["summary"]


def test_summary_cannot_reference_missing_citations() -> None:
    summarizer = _Summarizer("Only [3]")
    qdrant = _FakeQdrant(_points())
    app = create_rag_app(client=qdrant, summarizer=summarizer)
    client = TestClient(app)

    response = client.post("/rag", json={"query": "supply shocks"})

    assert response.status_code == 422
    assert "citations" in response.json()["detail"].lower()
