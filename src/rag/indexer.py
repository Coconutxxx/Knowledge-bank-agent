"""把文件加载、切分并写入向量库。"""

from __future__ import annotations

from pathlib import Path

from src.config import Settings, settings
from src.rag.document_loader import iter_supported_files, load_document
from src.rag.splitter import split_sections
from src.rag.vector_store import VectorStore


class KnowledgeIndexer:
    def __init__(
        self,
        store: VectorStore | None = None,
        config: Settings = settings,
    ):
        self.config = config
        self.store = store or VectorStore(config)

    def ingest(self, target: str | Path) -> dict[str, int]:
        files = iter_supported_files(target)
        total_sections = 0
        total_chunks = 0
        for file_path in files:
            sections = load_document(file_path)
            chunks = split_sections(
                sections,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
            total_sections += len(sections)
            total_chunks += self.store.add_chunks(chunks)
        return {
            "files": len(files),
            "sections": total_sections,
            "chunks": total_chunks,
        }

