from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    text: str
    page: int | None


class SimpleTextChunker:
    def __init__(self, chunk_size: int = 1200, overlap: int = 180) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split_pages(self, pages: list[tuple[int | None, str]]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        ordinal = 0
        for page, text in pages:
            normalized = " ".join(text.split())
            if not normalized:
                continue
            start = 0
            while start < len(normalized):
                end = min(start + self.chunk_size, len(normalized))
                chunk_text = normalized[start:end].strip()
                if chunk_text:
                    chunks.append(TextChunk(ordinal=ordinal, text=chunk_text, page=page))
                    ordinal += 1
                if end == len(normalized):
                    break
                start = max(0, end - self.overlap)
        return chunks
