import openai
from openai import AsyncOpenAI
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.embeddings.base import EmbeddingProvider

_NO_RETRY_ERRORS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_not_exception_type(_NO_RETRY_ERRORS),
        reraise=True,
    )
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict = {"model": settings.embedding_model, "input": texts}
        if settings.embedding_model.startswith("text-embedding-3"):
            kwargs["dimensions"] = settings.embedding_dimensions
        response = await self.client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]
