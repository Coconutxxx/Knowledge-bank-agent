from src.rag.document_loader import LoadedSection
from src.rag.splitter import split_section


def test_splitter_respects_size_and_overlap():
    section = LoadedSection(
        text="第一句。" * 500,
        source="sample.txt",
        location="全文",
    )
    chunks = split_section(section, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_short_text_is_one_chunk():
    section = LoadedSection(text="简短文本", source="a.txt", location="全文")
    chunks = split_section(section, chunk_size=100, chunk_overlap=20)
    assert len(chunks) == 1
    assert chunks[0].text == "简短文本"

