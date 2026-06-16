from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=30)


class SourceCitation(BaseModel):
    source_id: str
    document_id: UUID
    title: str
    path: str
    source_url: str | None
    page: int | None
    score: float | None


class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    path: str
    source_url: str | None
    page: int | None
    score: float
    text: str


class SearchResponse(BaseModel):
    results: list[SearchResult]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=30)
    conversation_id: UUID | None = None


class RagAnswer(BaseModel):
    answer: str
    citations: list[SourceCitation]


class ChatResponse(BaseModel):
    answer: str
    citations: list[SourceCitation]
    conversation_id: UUID
