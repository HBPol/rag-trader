"""RAG query endpoint backed by Qdrant search results."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import APIRouter, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from ragtrader_api.settings import ApiSettings, SettingsValidationError, get_settings
from ragtrader_api.vectorstore import DEFAULT_CLIENT_FACTORY, ClientFactory


class LlmSummarizer(Protocol):
    """Minimal protocol for summarizing snippets."""

    def summarize(self, *, query: str, snippets: Sequence[RagSnippet]) -> str: ...


class RagSnippet(BaseModel):
    """Serializable snippet returned from the vector store."""

    id: str
    title: str
    source: str
    published_at: str
    content: str
    citation: int
    score: float | None = None


class RagResponse(BaseModel):
    """Payload returned to the caller."""

    query: str
    summary: str
    snippets: list[RagSnippet]


class RagQuery(BaseModel):
    """Incoming request body."""

    query: str = Field(..., min_length=3, max_length=280)


class SummaryValidationError(ValueError):
    """Raised when the summary does not adhere to citation rules."""


class VectorSearchError(RuntimeError):
    """Raised when the vector store cannot fulfil a search request."""


def _coerce_iso8601(value: Any) -> str:
    if isinstance(value, datetime):
        timestamp = value
        if value.tzinfo is None:
            timestamp = value.replace(tzinfo=UTC)
        return timestamp.isoformat()
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat()
    return datetime.now(tz=UTC).isoformat()


def _validate_summary(summary: str, *, snippet_count: int) -> None:
    pattern = re.compile(r"\[(\d+)]")
    citations = [int(match) for match in pattern.findall(summary)]

    if snippet_count and not citations:
        raise SummaryValidationError(
            "Summary must include citations for retrieved snippets."
        )

    if any(citation < 1 for citation in citations):
        raise SummaryValidationError("Citations must start at 1.")

    if citations and max(citations) > snippet_count:
        raise SummaryValidationError(
            "Summary references more citations than available snippets."
        )


class TemplateSummarizer:
    """Deterministic summarizer used in tests and local development."""

    def summarize(self, *, query: str, snippets: Sequence[RagSnippet]) -> str:  # noqa: D401
        if not snippets:
            return f"No supporting context was found for: {query}"

        highlights = []
        for snippet in snippets:
            highlights.append(
                f"{snippet.title} from {snippet.source} relates to the query ["
                f"{snippet.citation}]"
            )
        return "; ".join(highlights)


class RagQueryService:
    """Handles retrieval and summarization for RAG requests."""

    def __init__(
        self,
        settings: ApiSettings,
        *,
        client: Any | None = None,
        client_factory: ClientFactory | None = None,
        summarizer: LlmSummarizer | None = None,
        max_snippets: int = 5,
    ) -> None:
        self.settings = settings
        self._client = client
        self._client_factory = client_factory or DEFAULT_CLIENT_FACTORY
        self._summarizer = summarizer or TemplateSummarizer()
        self.max_snippets = max_snippets

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"url": self.settings.qdrant_url}
        if self.settings.use_qdrant_cloud and self.settings.qdrant_api_key:
            kwargs["api_key"] = self.settings.qdrant_api_key
        return kwargs

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(**self._client_kwargs())
        return self._client

    def retrieve(self, *, query: str) -> RagResponse:
        try:
            results = self.client.search(
                collection_name=self.settings.qdrant_collection,
                query_text=query,
                limit=self.max_snippets,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            raise VectorSearchError("Vector search failed") from exc

        snippets: list[RagSnippet] = []
        for index, result in enumerate(results, start=1):
            payload = getattr(result, "payload", {}) or {}
            snippet = RagSnippet(
                id=str(getattr(result, "id", index)),
                title=str(payload.get("title") or "Untitled"),
                source=str(payload.get("source") or "unknown"),
                published_at=_coerce_iso8601(payload.get("published_at")),
                content=str(payload.get("content") or payload.get("text") or ""),
                score=(
                    float(getattr(result, "score", 0.0))
                    if hasattr(result, "score")
                    else None
                ),
                citation=index,
            )
            snippets.append(snippet)

        summary = self._summarizer.summarize(query=query, snippets=snippets)
        _validate_summary(summary, snippet_count=len(snippets))
        return RagResponse(query=query, summary=summary, snippets=snippets)


def _build_router(service: RagQueryService) -> APIRouter:
    router = APIRouter()

    @router.post("/rag", response_model=RagResponse)
    async def rag_query(payload: RagQuery) -> RagResponse:
        try:
            return service.retrieve(query=payload.query)
        except SummaryValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except VectorSearchError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    return router


def create_rag_app(
    *,
    settings: ApiSettings | None = None,
    client: Any | None = None,
    client_factory: ClientFactory | None = None,
    summarizer: LlmSummarizer | None = None,
    max_snippets: int = 5,
) -> FastAPI:
    resolved_settings = settings
    if resolved_settings is None:
        if client is not None or client_factory is not None:
            resolved_settings = ApiSettings(
                require_database=False,
                require_vector_store=False,
            )
        else:
            try:
                resolved_settings = get_settings()
            except (
                SettingsValidationError
            ) as exc:  # pragma: no cover - configuration guard
                raise RuntimeError("Invalid API settings") from exc

    service = RagQueryService(
        resolved_settings,
        client=client,
        client_factory=client_factory,
        summarizer=summarizer,
        max_snippets=max_snippets,
    )
    app = FastAPI(title="RAGTrader Retrieval")
    app.include_router(_build_router(service))
    return app


def create_rag_router(
    *,
    settings: ApiSettings | None = None,
    client_factory: ClientFactory | None = None,
    summarizer: LlmSummarizer | None = None,
    max_snippets: int = 5,
) -> APIRouter:
    resolved_settings = settings if settings is not None else get_settings()
    service = RagQueryService(
        resolved_settings,
        client_factory=client_factory,
        summarizer=summarizer,
        max_snippets=max_snippets,
    )
    return _build_router(service)


__all__ = [
    "LlmSummarizer",
    "RagQuery",
    "RagQueryService",
    "RagResponse",
    "RagSnippet",
    "SummaryValidationError",
    "TemplateSummarizer",
    "VectorSearchError",
    "create_rag_app",
    "create_rag_router",
]
