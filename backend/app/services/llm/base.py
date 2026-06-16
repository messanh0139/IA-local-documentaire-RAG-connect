from abc import ABC, abstractmethod

from app.schemas.search import SourceCitation


class RagGenerator(ABC):
    @abstractmethod
    async def generate(self, question: str, context: str, citations: list[SourceCitation]) -> str:
        raise NotImplementedError
