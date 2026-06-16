from app.core.config import settings
from app.services.llm.base import RagGenerator
from app.services.llm.mock import MockRagGenerator
from app.services.llm.openai_provider import OpenAIRagGenerator


def build_rag_generator() -> RagGenerator:
    if settings.llm_provider == "mock":
        return MockRagGenerator()
    if settings.llm_provider == "openai":
        return OpenAIRagGenerator()
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
