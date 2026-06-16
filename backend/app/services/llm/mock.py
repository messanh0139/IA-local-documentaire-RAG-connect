from app.schemas.search import SourceCitation
from app.services.llm.base import RagGenerator


class MockRagGenerator(RagGenerator):
    async def generate(self, question: str, context: str, citations: list[SourceCitation]) -> str:
        if not citations:
            return (
                "Je n'ai pas trouvé de source accessible permettant de répondre. "
                "Ajoutez des documents ou vérifiez vos permissions."
            )
        source_list = ", ".join(f"[{citation.source_id}]" for citation in citations)
        preview = context[:700].strip()
        return (
            "Mode développement sans LLM configuré. "
            f"Question reçue: {question}\n\n"
            f"Sources accessibles récupérées: {source_list}.\n\n"
            f"Extrait du contexte:\n{preview}\n\n"
            "Configure LLM_PROVIDER=openai pour générer une réponse finale."
        )
