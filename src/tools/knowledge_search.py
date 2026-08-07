"""供 ReAct Agent 调用的知识库检索工具。"""

from __future__ import annotations

from src.rag.vector_store import SearchResult, VectorStore


class KnowledgeSearchTool:
    name = "knowledge_search"
    description = (
        "在本地知识库中进行语义检索。输入应是简洁、完整的检索问题或关键词。"
        "当用户询问文档、业务知识、制度、SQL、研究资料等内容时必须调用。"
    )

    def __init__(self, store: VectorStore):
        self.store = store
        self.last_results: list[SearchResult] = []

    def run(self, query: str) -> str:
        self.last_results = self.store.search(query)
        if not self.last_results:
            return "知识库为空，或没有检索到任何内容。请明确告诉用户当前证据不足。"

        blocks = []
        for number, item in enumerate(self.last_results, start=1):
            blocks.append(
                f"[来源{number}] {item.citation}\n{item.text}"
            )
        return "\n\n".join(blocks)

