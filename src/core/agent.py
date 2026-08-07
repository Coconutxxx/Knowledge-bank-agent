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


SYSTEM_PROMPT = """
你是一个SQL知识库问答助手。

系统会给你用户问题以及本地知识库检索结果。

你必须判断检索结果是否能够直接支持回答。

状态输出规则：
1. 如果检索结果中存在与用户功能需求直接相关的SQL语句，
   回答第一行必须输出：[KB_HIT]
2. 如果检索结果不能直接支持用户问题，需要生成通用SQL模板，
   回答第一行必须输出：[KB_MISS]
3. [KB_HIT]时，可以使用[来源1]、[来源2]等引用。
4. [KB_MISS]时，不得使用任何[来源X]引用，也不要声称通用模板来自知识库。
5. 状态标记后再输出正常中文回答。
6. 不要展示思维过程。

判断标准：
- 功能主题与用户问题直接对应，才算KB_HIT。
- 仅表名、字段名、SQL正文中的单词相似，不算直接对应。
- 如果只是参考检索结果后自行推测表结构，仍然算KB_MISS。

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
11. 可以根据各来源与用户问题的直接相关程度调整回答顺序，不要求按照来源1、来源2、来源3的顺序回答。
12. 来源编号是固定的。无论调整到回答中的哪个位置，都必须保留其原始来源编号，禁止重新编号。
13. 不要求使用全部检索来源，只引用真正有助于回答用户问题的来源。
14. 如果引用某个来源并展示其SQL，必须从该来源逐字复制，不得使用其他来源的SQL。
15. 如果展示某来源的SQL，应完整保留该来源中的SQL语句，不得随意截断、改写或拼接。
16. 回答中的[来源N]必须与“查看检索来源”中的来源N保持一致。
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

    sources: list[SearchResult] = field(
        default_factory=list
    )

    trace: list[dict[str, str]] = field(
        default_factory=list
    )

    # True：答案使用了知识库依据
    # False：答案是DeepSeek生成的通用模板
    used_knowledge: bool = False

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
    def _parse_knowledge_status(
        raw_answer: str,
    ) -> tuple[str, bool]:
        """
        解析DeepSeek返回的知识库使用状态，
        并从最终答案中移除内部状态标记。
        """

        raw_answer = str(
            raw_answer or ""
        ).strip()

        status_match = re.match(
            r"^\s*\[KB_(HIT|MISS)\]\s*",
            raw_answer,
            flags=re.IGNORECASE,
        )

        if not status_match:
            # 没有正确返回状态时采用保守策略：
            # 不显示检索来源
            return raw_answer, False

        status = (
            status_match.group(1)
            .strip()
            .upper()
        )

        cleaned_answer = re.sub(
            r"^\s*\[KB_(?:HIT|MISS)\]\s*",
            "",
            raw_answer,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

        used_knowledge = (
            status == "HIT"
        )

        return (
            cleaned_answer,
            used_knowledge,
        )

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

    def run(
        self,
        question: str,
    ) -> AgentResult:
        question = str(
            question or ""
        ).strip()

        if not question:
            return AgentResult(
                answer="请输入你想查询的问题。",
                sources=[],
                trace=[],
                used_knowledge=False,
            )

        # =====================================================
        # 第一种情况：普通问候
        # =====================================================

        if self._is_greeting(question):
            answer = (
                "你好！我是SQL知识库问答助手。"
                "你可以告诉我想查询的业务功能，"
                "我会优先从知识库中查找相关SQL；"
                "如果知识库没有相关内容，"
                "我也可以提供通用SQL模板。"
            )

            self.memory.add_turn(
                question,
                answer,
            )

            return AgentResult(
                answer=answer,
                sources=[],
                trace=[
                    {
                        "event": "greeting",
                        "detail": "普通问候",
                    }
                ],
                used_knowledge=False,
            )

        # =====================================================
        # 第二步：本地知识库检索
        # =====================================================

        self.tool.run(
            question
        )

        sources = self._deduplicate_sources(
            self.tool.last_results
        )[:3]

        # 获取最相似结果的距离
        best_distance = None

        if sources:
            best_distance = (
                sources[0].distance
            )

        # 初步判断检索结果是否达到距离阈值
        has_reliable_evidence = (
            best_distance is not None
            and best_distance
            <= self.config.retrieval_distance_threshold
        )

        # =====================================================
        # 路线一：存在可能可靠的知识库结果
        # =====================================================

        if has_reliable_evidence:
            observation = (
                self._format_observation(
                    sources
                )
            )

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                *self.memory.messages(),
                {
                    "role": "user",
                    "content": (
                        f"用户问题：\n"
                        f"{question}\n\n"
                        f"本地知识库检索结果：\n"
                        f"{observation}"
                    ),
                },
            ]

            # 有候选依据时关闭深度思考，
            # 让DeepSeek判断这些内容是否真正相关
            raw_answer = self.llm.chat(
                messages,
                thinking=False,
            ).strip()

            answer, used_knowledge = (
                self._parse_knowledge_status(
                    raw_answer
                )
            )

            # DeepSeek最终判断知识库不相关时，
            # 不把候选来源返回给页面
            if not used_knowledge:
                sources = []

                trace = [
                    {
                        "event": "generic_sql",
                        "detail": (
                            "向量检索存在候选结果，"
                            "但模型判断其不能直接支持回答，"
                            "因此不展示检索来源。"
                        ),
                    }
                ]

            else:
                trace = [
                    {
                        "event": "knowledge_search",
                        "detail": (
                            f"命中知识库，最佳距离："
                            f"{best_distance:.4f}"
                        ),
                    }
                ]

        # =====================================================
        # 路线二：没有达到距离阈值
        # =====================================================

        else:
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

            # 没有可靠知识库依据时，
            # 使用DeepSeek思考模式生成通用模板
            answer = self.llm.chat(
                messages,
                thinking=True,
            ).strip()

            # 通用模板不展示任何知识库来源
            sources = []
            used_knowledge = False

            distance_text = (
                f"{best_distance:.4f}"
                if best_distance is not None
                else "无结果"
            )

            trace = [
                {
                    "event": "generic_sql",
                    "detail": (
                        f"知识库证据不足，"
                        f"最佳距离：{distance_text}，"
                        f"已生成通用SQL。"
                    ),
                }
            ]

        # =====================================================
        # 最终结果处理
        # =====================================================

        if not answer:
            answer = (
                "模型没有生成有效回答，"
                "请换一种问法后重试。"
            )

            sources = []
            used_knowledge = False

        self.memory.add_turn(
            question,
            answer,
        )

        return AgentResult(
            answer=answer,
            sources=sources,
            trace=trace,
            used_knowledge=used_knowledge,
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