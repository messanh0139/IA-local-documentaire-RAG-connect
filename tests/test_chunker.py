from app.services.ingestion.chunker import SimpleTextChunker


def test_chunker_splits_with_overlap() -> None:
    chunker = SimpleTextChunker(chunk_size=10, overlap=2)
    chunks = chunker.split_pages([(3, "abcdefghijklmnopqrstuvwxyz")])

    assert len(chunks) == 3
    assert chunks[0].text == "abcdefghij"
    assert chunks[1].text.startswith("ij")
    assert all(chunk.page == 3 for chunk in chunks)
