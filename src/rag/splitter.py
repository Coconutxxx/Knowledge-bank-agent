"""不依赖 LangChain 的轻量文本切分器。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.rag.document_loader import LoadedSection


@dataclass(frozen=True)
class TextChunk:
    text: str
    source: str
    location: str
    chunk_index: int


def _preferred_cut(text: str, start: int, end: int, minimum: int) -> int:
    """尽量在换行或中英文句号后切分，避免把一句话从中间截断。"""
    window = text[minimum:end]
    matches = list(re.finditer(r"[\n。！？!?；;]", window))
    if matches:
        return minimum + matches[-1].end()
    return end


def split_section(
    section: LoadedSection,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap 必须满足 0 <= overlap < chunk_size")

    text = re.sub(r"\n{3,}", "\n\n", section.text).strip()
     # Excel中的一条SQL记录作为一个完整文本块保存
    if "｜SQL_ID：" in section.location:
        return [
            TextChunk(
                text=text,
                source=section.source,
                location=section.location,
                chunk_index=0,
            )
        ]
    chunks = []
    start = 0
    index = 0
    
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        if hard_end < len(text):
            minimum = start + max(chunk_size // 2, chunk_size - 160)
            end = _preferred_cut(text, start, hard_end, minimum)
        else:
            end = hard_end

        content = text[start:end].strip()
        if content:
            chunks.append(
                TextChunk(
                    text=content,
                    source=section.source,
                    location=section.location,
                    chunk_index=index,
                )
            )
            index += 1

        if end >= len(text):
            break
        next_start = end - chunk_overlap
        start = next_start if next_start > start else end

    return chunks


def split_sections(
    sections: list[LoadedSection],
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> list[TextChunk]:
    chunks = []
    for section in sections:
        chunks.extend(split_section(section, chunk_size, chunk_overlap))
    return chunks

