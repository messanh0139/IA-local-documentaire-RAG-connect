from app.core.config import settings
from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.mock import MockEmbeddingProvider
from app.services.embeddings.openai_provider import OpenAIEmbeddingProvider


def build_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider(dimensions=settings.embedding_dimensions)
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
