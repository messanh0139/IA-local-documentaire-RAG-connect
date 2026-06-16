import openai
from openai import AsyncOpenAI
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.schemas.search import SourceCitation
from app.services.llm.base import RagGenerator
from app.services.rag.prompts import SYSTEM_PROMPT

_NO_RETRY_ERRORS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.UnprocessableEntityError,
)


class OpenAIRagGenerator(RagGenerator):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_not_exception_type(_NO_RETRY_ERRORS),
        reraise=True,
    )
    async def generate(self, question: str, context: str, citations: list[SourceCitation]) -> str:
        if not citations or not context.strip():
            return "Je n'ai pas trouvé de source accessible permettant de répondre à cette question."

        citation_hint = "\n".join(
            f"[{item.source_id}] {item.title} - {item.path} - page {item.page or 'n/a'}"
            for item in citations
        )
        response = await self.client.responses.create(
            model=settings.llm_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Sources disponibles:\n{citation_hint}\n\n"
                        f"Contexte autorisé:\n{context}"
                    ),
                },
            ],
        )
        answer = response.output_text.strip()
        if not answer:
            return "Je n'ai pas pu générer de réponse à partir des sources disponibles."
        return answer
