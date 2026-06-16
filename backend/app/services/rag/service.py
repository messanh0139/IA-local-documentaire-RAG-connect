from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import Principal
from app.schemas.search import (
    ChatRequest,
    RagAnswer,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceCitation,
)
from app.services.audit import AuditService
from app.services.embeddings.factory import build_embedding_provider
from app.services.llm.factory import build_rag_generator
from app.services.permissions import PermissionService
from app.services.vector.qdrant_store import QdrantVectorStore, VectorSearchHit


class RagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embeddings = build_embedding_provider()
        self.vector_store = QdrantVectorStore()
        self.permissions = PermissionService()
        self.generator = build_rag_generator()

    async def search(self, request: SearchRequest, principal: Principal) -> SearchResponse:
        query_vector = await self.embeddings.embed_query(request.query)
        hits = self.vector_store.search(query_vector, principal, limit=request.top_k * 4)
        safe_hits = self._filter_accessible_hits(hits, principal)[: request.top_k]
        await AuditService(self.db).record(
            principal=principal,
            action="search",
            resource_type="rag",
            metadata={
                "query": request.query,
                "top_k": request.top_k,
                "returned_chunks": len(safe_hits),
            },
        )
        return SearchResponse(results=[self._hit_to_result(hit) for hit in safe_hits])

    async def answer(self, request: ChatRequest, principal: Principal) -> RagAnswer:
        search_response = await self.search(
            SearchRequest(query=request.question, top_k=request.top_k),
            principal,
        )
        citations = [
            SourceCitation(
                source_id=f"S{index}",
                document_id=result.document_id,
                title=result.title,
                path=result.path,
                source_url=result.source_url,
                page=result.page,
                score=result.score,
            )
            for index, result in enumerate(search_response.results, start=1)
        ]
        context = self._build_context(search_response.results)
        answer = await self.generator.generate(request.question, context, citations)
        await AuditService(self.db).record(
            principal=principal,
            action="chat",
            resource_type="rag",
            metadata={
                "question": request.question,
                "citations": [str(citation.document_id) for citation in citations],
            },
        )
        return RagAnswer(answer=answer, citations=citations)

    def _filter_accessible_hits(
        self,
        hits: list[VectorSearchHit],
        principal: Principal,
    ) -> list[VectorSearchHit]:
        safe_hits: list[VectorSearchHit] = []
        for hit in hits:
            if self.permissions.payload_is_accessible(hit.payload, principal):
                safe_hits.append(hit)
        return safe_hits

    def _hit_to_result(self, hit: VectorSearchHit) -> SearchResult:
        payload = hit.payload
        return SearchResult(
            chunk_id=UUID(payload["chunk_id"]),
            document_id=UUID(payload["document_id"]),
            title=payload.get("title") or "Document",
            path=payload.get("path") or "",
            source_url=payload.get("source_url"),
            page=payload.get("page"),
            score=hit.score,
            text=payload.get("chunk_text") or "",
        )

    def _build_context(self, results: list[SearchResult]) -> str:
        parts: list[str] = []
        remaining = settings.rag_max_context_chars
        for index, result in enumerate(results, start=1):
            header = (
                f"[S{index}] title={result.title}; path={result.path}; "
                f"page={result.page or 'n/a'}; url={result.source_url or 'n/a'}"
            )
            text = result.text.strip()
            block = f"{header}\n{text}"
            if len(block) > remaining:
                block = block[:remaining]
            if block:
                parts.append(block)
                remaining -= len(block)
            if remaining <= 0:
                break
        return "\n\n".join(parts)
