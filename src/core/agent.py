"""基于文章 ReAct 思路实现的知识库问答 Agent。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.config import Settings, settings
from src.core.llm_client import LLMClient
from src.memory.conversation import ConversationMemory
from src.rag.vector_store import SearchResult, VectorStore
from src.tools.knowledge_search import KnowledgeSearchTool


SYSTEM_PROMPT = """你是一个SQL知识库问答助手。

系统已经根据用户问题在本地知识库中完成检索，并把检索结果提供给你。

回答规则：
1. 优先依据知识库中的“功能主题”和“SQL正文”回答。
2. 如果知识库提供了完整SQL，优先保留原始SQL，不要随意修改表名、字段名和业务条件。
3. 如果检索结果不完整，但提供了部分表、字段或SQL：
   - 先说明“根据现有知识库，可能涉及以下表和字段”；
   - 给出能够确认的表和字段；
   - 再根据已有信息生成一份通用Hive SQL模板；
   - 未确定的信息使用<表名>、<字段名>、<关联条件>等占位符。
4. 不要因为资料标记为“不完整”就直接拒绝回答。
5. 不要向用户罗列“缺失表”“未登记字段”“字段归属不明”等内部检查信息。
6. 通用SQL必须明确标注为“通用模板”，不能假装是知识库中的原始SQL。
7. 不得虚构真实业务表名、字段名和统计口径。
8. 引用知识库内容时使用[来源1]、[来源2]形式。
9. 最多引用3个真正相关的来源。
10. 直接输出最终中文回答，不要输出JSON，不要展示思维过程。
"""

GENERIC_SQL_PROMPT = """你是一个SQL生成助手。

本地知识库没有检索到足够可靠的依据。请根据用户问题提取业务关键词，并生成一个通用SQL示例。

要求：
1. 首先明确说明：“当前知识库没有检索到可靠依据，以下是通用SQL示例。”
2. 从用户问题中提取查询对象、筛选条件、关联关系、统计指标、时间范围等关键词。
3. 如果用户明确指定Hive SQL，则使用Hive SQL。
4. 如果用户没有指定数据库类型，默认使用Hive SQL。
5. 不允许编造真实的业务表名和字段名。
6. 未知表名和字段名必须使用占位符，例如：
   <主表名>
   <用户号码字段>
   <日期字段>
7. 在SQL后列出“需要用户确认的信息”，例如真实表名、字段名和统计口径。
8. SQL只能作为通用模板，不能声称来自知识库。
9. 如果用户的问题并不是SQL需求，不要强行生成SQL，应说明知识库依据不足并请用户补充资料。
"""


@dataclass
class AgentResult:
    answer: str
    sources: list[SearchResult] = field(default_factory=list)
    trace: list[dict[str, str]] = field(default_factory=list)


class KnowledgeAgent:
    def __init__(
        self,
        store: VectorStore | None = None,
        llm: LLMClient | None = None,
        config: Settings = settings,
    ):
        self.config = config
        self.store = store or VectorStore(config)
        self.llm = llm or LLMClient(config)
        self.memory = ConversationMemory(max_turns=8)
        self.tool = KnowledgeSearchTool(self.store)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _deduplicate_sources(sources: list[SearchResult]) -> list[SearchResult]:
        unique = []
        seen = set()
        for item in sources:
            key = (item.source, item.location, item.chunk_index)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    @staticmethod
    def _format_observation(
        results: list[SearchResult],
    ) -> str:
        if not results:
            return (
                "知识库为空，或者没有检索到相关内容。"
                "请根据用户需求提供通用SQL模板。"
            )
        blocks = []
        for number, item in enumerate(results, start=1):
            blocks.append(
                f"[来源{number}] {item.citation}\n"
                f"{item.text}"
            )
        return "\n\n".join(blocks)

    def run(self, question: str) -> AgentResult:
        if self._is_greeting(question):
            answer = (
                "你好！我是本地 SQL 知识库助手。"
                "你可以向我询问某项业务功能涉及的表、字段或 SQL，"
                "例如“怎么查询直销客户类型？”或“查询日期使用什么SQL？”。"
                "请问有什么可以帮你？"
            )

            self.memory.add_turn(question, answer)

            return AgentResult(
                answer=answer,
                sources=[],
                trace=[{"event": "greeting", "detail": "普通问候"}],
            )
        
        # 第一步：在本地知识库检索
        self.tool.run(question)

        sources = self._deduplicate_sources(
        self.tool.last_results)[:3]

        # 获取最相似片段的距离
        best_distance = None

        if sources:
            best_distance = sources[0].distance

        # 判断知识库证据是否足够可靠
        has_reliable_evidence = (
        best_distance is not None
        and best_distance
        <= self.config.retrieval_distance_threshold)

        if has_reliable_evidence:
        # 路线一：有可靠依据
            observation = self._format_observation(
                sources)

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                *self.memory.messages(),
                {
                    "role": "user",
                    "content": (
                        f"用户问题：\n{question}\n\n"
                        f"本地知识库检索结果：\n{observation}"
                    ),
                },
            ]

            # 有依据时关闭深度思考，快速整理答案
            answer = self.llm.chat(
                messages,
                thinking=False,
            ).strip()

            trace = [
                {
                    "event": "knowledge_search",
                    "detail": (
                        f"命中知识库，最佳距离："
                        f"{best_distance:.4f}"
                    ),
                }
            ]

        else:
            # 路线二：没有可靠依据
            messages = [
                {
                    "role": "system",
                    "content": GENERIC_SQL_PROMPT,
                },
                *self.memory.messages(),
                {
                    "role": "user",
                    "content": question,
                },
            ]

            # 没有依据时开启DeepSeek思考模式
            answer = self.llm.chat(
                messages,
                thinking=True,
            ).strip()

            # 通用SQL不是知识库内容，所以不展示无关来源
            sources = []

            distance_text = (
                f"{best_distance:.4f}"
                if best_distance is not None
                else "无结果"
            )

            trace = [
                {
                    "event": "generic_sql",
                    "detail": (
                        f"知识库证据不足，最佳距离："
                        f"{distance_text}，已生成通用SQL"
                    ),
                }
            ]

        if not answer:
            answer = "模型没有生成有效回答，请换一种问法后重试。"

        self.memory.add_turn(question, answer)

        return AgentResult(
            answer=answer,
            sources=sources,
            trace=trace,
        )

    def reset_memory(self) -> None:
        self.memory.clear()

    @staticmethod
    def _is_greeting(question: str) -> bool:
        normalized = (
            question.strip()
            .lower()
            .replace("！", "")
            .replace("!", "")
            .replace("？", "")
            .replace("?", "")
            .replace("。", "")
        )

        greetings = {
            "hello",
            "hi",
            "hey",
            "你好",
            "您好",
            "嗨",
            "在吗",
            "早上好",
            "下午好",
            "晚上好",
        }

        return normalized in greetings