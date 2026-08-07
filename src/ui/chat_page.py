from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
import unicodedata
import sqlparse
from src.core.agent import KnowledgeAgent
from src.config import settings
from src.rag.vector_store import SearchResult, VectorStore


@st.cache_resource
def get_vector_store() -> VectorStore:
    return VectorStore()


def get_knowledge_agent() -> KnowledgeAgent:
    if "knowledge_agent" not in st.session_state:
        st.session_state["knowledge_agent"] = KnowledgeAgent(
            store=get_vector_store()
        )

    return st.session_state["knowledge_agent"]

def clear_chat() -> None:
    agent = st.session_state.get(
        "knowledge_agent"
    )

    if agent is not None:
        agent.reset_memory()

    st.session_state["messages"] = []
    st.session_state["pending_question"] = None

def extract_worksheet(location: str) -> str:
    patterns = [
        r"工作表[：:]\s*([^|]+)",
        r"sheet[：:]\s*([^|]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, location, flags=re.IGNORECASE)

        if match:
            return match.group(1).strip()

    return ""


def extract_sql_id(text: str, location: str) -> str:
    combined_text = f"{location}\n{text}"

    patterns = [
        r"SQL_ID[：:=\s]+(\d+)",
        r"sql_id[：:=\s]+(\d+)",
        r"序号[：:=\s]+(\d+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            combined_text,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return ""

def extract_sql_text(
    text: str,
) -> str:
    """
    从知识记录中提取SQL正文，
    排除“SQL正文开始”和“SQL正文结束”标记。
    """

    if not text:
        return ""

    # 优先提取结构化SQL正文
    sql_block = re.search(
        (
            r"SQL正文开始\s*"
            r"(.*?)"
            r"\s*SQL正文结束"
        ),
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if sql_block:
        return sql_block.group(1).strip()

    # 兼容旧索引
    sql_match = re.search(
        (
            r"(?is)\b("
            r"select|with|insert|update|delete|"
            r"create|alter|drop|merge"
            r")\b.*"
        ),
        text,
    )

    if not sql_match:
        return ""

    result = sql_match.group(0).strip()

    # 旧数据可能仍带有结束标记
    result = re.sub(
        r"\s*SQL正文结束\s*$",
        "",
        result,
        flags=re.IGNORECASE,
    )

    return result.strip()

def normalize_sql_for_display(
    sql_text: str,
) -> str:
    """
    清理Excel带入的异常空格，
    并重新格式化SQL用于页面展示。

    该函数只修改显示文本，
    不修改数据库中的原始SQL。
    """

    if not sql_text:
        return ""

    text = str(sql_text)

    # 统一全角字符、全角空格、特殊空格
    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    # 统一换行符
    text = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\t", "    ")
    )

    # 删除零宽空格、BOM等不可见字符
    text = re.sub(
        r"[\u200b-\u200d\u2060\ufeff]",
        "",
        text,
    )

    # 将各种Unicode空格替换为普通半角空格
    text = re.sub(
        (
            r"[\u00a0\u1680"
            r"\u2000-\u200a"
            r"\u202f\u205f\u3000]"
        ),
        " ",
        text,
    )

    # 删除SQL正文的内部标记
    text = re.sub(
        r"^\s*SQL正文开始\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*SQL正文结束\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # 将连续多个空白行压缩为一个空白行
    text = re.sub(
        r"\n[ \t]*\n(?:[ \t]*\n)+",
        "\n\n",
        text,
    ).strip()

    if not text:
        return ""

    try:
        # 分割同一记录中的多条SQL语句
        statements = sqlparse.split(
            text
        )

        formatted_statements: list[str] = []

        for statement in statements:
            statement = statement.strip()

            if not statement:
                continue

            formatted = sqlparse.format(
                statement,
                reindent=True,
                strip_whitespace=True,
                use_space_around_operators=True,
                indent_width=4,
            ).strip()

            if formatted:
                formatted_statements.append(
                    formatted
                )

        if formatted_statements:
            return "\n\n".join(
                formatted_statements
            )

    except Exception:
        # 格式化失败时使用保底清理
        pass

    # 保底方案：删除每行所有异常前导空白
    cleaned_lines: list[str] = []

    for line in text.splitlines():
        cleaned_line = re.sub(
            r"^\s+",
            "",
            line.rstrip(),
        )

        if cleaned_line:
            cleaned_lines.append(
                cleaned_line
            )
        elif (
            cleaned_lines
            and cleaned_lines[-1] != ""
        ):
            cleaned_lines.append("")

    return "\n".join(
        cleaned_lines
    ).strip()

def normalize_answer_sql_blocks(
    answer: str,
) -> str:
    """
    格式化DeepSeek回答中的SQL代码块。

    只处理SQL、Hive、HQL代码块，
    不影响回答中的普通文字。
    """

    if not answer:
        return ""

    answer = str(answer)

    code_block_pattern = re.compile(
        (
            r"```"
            r"(?P<language>[^\n`]*)"
            r"\n"
            r"(?P<code>.*?)"
            r"```"
        ),
        flags=re.DOTALL,
    )

    def replace_code_block(
        match: re.Match,
    ) -> str:
        language = (
            match.group("language")
            .strip()
            .lower()
        )

        code = (
            match.group("code")
            .strip()
        )

        sql_languages = {
            "",
            "sql",
            "hive",
            "hql",
            "hive sql",
            "hivesql",
        }

        # 有明确的非SQL语言标记时不处理
        if language not in sql_languages:
            return match.group(0)

        # 没有语言标记时，检查是否确实为SQL
        if not language:
            is_sql = re.search(
                (
                    r"(?im)^\s*"
                    r"(?:--[^\n]*\n\s*)*"
                    r"(select|with|insert|update|"
                    r"delete|create|alter|drop|merge)"
                    r"\b"
                ),
                code,
            )

            if not is_sql:
                return match.group(0)

        formatted_sql = (
            normalize_sql_for_display(
                code
            )
        )

        if not formatted_sql:
            return match.group(0)

        return (
            "```sql\n"
            f"{formatted_sql}\n"
            "```"
        )

    return code_block_pattern.sub(
        replace_code_block,
        answer,
    )

def extract_function_theme(
    text: str,
) -> str:
    """从知识记录正文中提取功能主题。"""

    if not text:
        return "未填写"

    match = re.search(
        r"(?im)^\s*功能主题\s*[:：]\s*(.*?)\s*$",
        text,
    )

    if match:
        return match.group(1).strip()

    return "未填写"

def serialize_source(
    source: SearchResult,
) -> dict[str, str]:
    """将检索结果转换为可保存的普通字典。"""

    source_text = source.text or ""
    source_location = source.location or ""
    source_name = (
        source.source or "未知来源"
    )

    function_theme = (
        str(source.function_theme).strip()
        if source.function_theme
        else extract_function_theme(
            source_text
        )
    )

    return {
        # Excel文件名
        "workbook": Path(
            source_name
        ).name,

        # 功能主题
        "function_theme": (
            function_theme or "未填写"
        ),

        # SQL_ID
        "sql_id": (
            str(source.sql_id).strip()
            if source.sql_id
            else extract_sql_id(
                source_location,
                source_text,
            )
        ),

        # SQL正文
        "sql": extract_sql_text(
            source_text
        ),
    }

def display_sources(
    sources: list[dict],
) -> None:
    """
    显示检索来源。

    格式：
    Excel文件名｜功能主题｜SQL_ID
    """

    if not sources:
        return

    with st.expander(
        "查看检索来源"
    ):
        for number, original_source in enumerate(
            sources,
            start=1,
        ):
            source = normalize_saved_source(
                original_source
            )

            st.markdown(
                (
                    f"**来源 {number}：** "
                    f"{source['workbook']}"
                    f"｜{source['function_theme']}"
                    f"｜SQL_ID：{source['sql_id']}"
                )
            )

            sql_text = normalize_sql_for_display(
                source["sql"]
            )
            if sql_text:
                st.code(
                    sql_text,
                    language="sql",
                    wrap_lines=True,
                )
            else:
                st.caption(
                    "该来源没有识别到SQL正文。"
                )

            if number < len(sources):
                st.divider()

def render_chat_page() -> None:
    st.title("📚 SQL 知识库问答 Agent")
    st.caption("数据库知识 → 本地向量检索 → DeepSeek 组织答案")

    try:
        vector_store = get_vector_store()
        indexed_count = vector_store.count()
    except Exception:
        indexed_count = 0

    metric_col1, metric_col2, metric_col3, metric_col4 = (
        st.columns(4))

    with metric_col1:
        st.metric("已索引文本块", indexed_count)

    with metric_col2:
        st.metric("聊天模型", settings.model_name)

    with metric_col3:
        st.metric(
            "交给模型的来源",
            settings.final_context_k,
        )

    with metric_col4:
        st.metric(
            "页面展示来源",
            settings.display_source_k,
        )

    if st.button(
        "清空当前对话"
    ):
        clear_chat()
        st.rerun()

    # =====================================================
    # 初始化对话状态
    # =====================================================

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    if (
        "pending_question"
        not in st.session_state
    ):
        st.session_state[
            "pending_question"
        ] = None

    # 使用固定容器显示全部对话，
    # 避免rerun时新旧消息组件位置变化
    chat_container = st.container()

    # =====================================================
    # 统一显示历史消息
    # =====================================================

    with chat_container:
        for message in (
            st.session_state["messages"]
        ):
            role = message.get(
                "role",
                "assistant",
            )

            message_content = str(
                message.get(
                    "content",
                    "",
                )
                or ""
            )

            if role == "assistant":
                message_content = (
                    normalize_answer_sql_blocks(
                        message_content
                    )
                )

            with st.chat_message(role):
                st.markdown(
                    message_content
                )

                if role == "assistant":
                    message_sources = (
                        message.get(
                            "sources",
                            [],
                        )
                    )

                    if message_sources:
                        display_sources(
                            message_sources
                        )

    # =====================================================
    # 接收新问题
    # =====================================================

    pending_question = (
        st.session_state[
            "pending_question"
        ]
    )

    user_question = st.chat_input(
        "请输入你想查询的问题",
        disabled=(
            pending_question is not None
        ),
    )

    # 收到问题后先保存，再立即rerun。
    # 不在当前这一次运行中重复显示消息。
    if (
        user_question
        and pending_question is None
    ):
        cleaned_question = (
            str(user_question).strip()
        )

        if cleaned_question:
            st.session_state[
                "messages"
            ].append(
                {
                    "role": "user",
                    "content": (
                        cleaned_question
                    ),
                }
            )

            st.session_state[
                "pending_question"
            ] = cleaned_question

            st.rerun()

    # 没有等待处理的问题时结束
    if pending_question is None:
        return

    # =====================================================
    # 处理等待中的问题
    # =====================================================

    assistant_message: dict[
        str,
        object,
    ]

    with chat_container:
        with st.chat_message(
            "assistant"
        ):
            try:
                with st.spinner(
                    "Agent 正在检索知识库"
                    "并组织答案……"
                ):
                    agent = (
                        get_knowledge_agent()
                    )

                    result = agent.run(
                        pending_question
                    )

                answer = (
                    normalize_answer_sql_blocks(
                        result.answer
                    )
                )

                if result.used_knowledge:
                    serializable_sources = [
                        serialize_source(
                            source
                        )
                        for source
                        in result.sources[
                            :settings
                            .display_source_k
                        ]
                    ]

                else:
                    serializable_sources = []

                st.markdown(
                    answer
                )

                if serializable_sources:
                    display_sources(
                        serializable_sources
                    )

                assistant_message = {
                    "role": "assistant",
                    "content": answer,
                    "sources": (
                        serializable_sources
                    ),
                }

            except Exception as exc:
                error_message = (
                    f"运行失败：{exc}"
                )

                st.error(
                    error_message
                )

                assistant_message = {
                    "role": "assistant",
                    "content": error_message,
                    "sources": [],
                }

    # =====================================================
    # 保存本轮回答并重新稳定渲染页面
    # =====================================================

    st.session_state[
        "messages"
    ].append(
        assistant_message
    )

    st.session_state[
        "pending_question"
    ] = None

    # 再次rerun后，用户问题和助手回答
    # 都只会通过历史消息循环显示一次
    st.rerun()

def normalize_saved_source(
    source: dict,
) -> dict[str, str]:
    """统一新旧检索来源格式。"""

    source_text = str(
        source.get("text", "")
        or ""
    )

    citation = str(
        source.get("citation", "")
        or ""
    )

    workbook = str(
        source.get("workbook", "")
        or ""
    ).strip()

    function_theme = str(
        source.get(
            "function_theme",
            "",
        )
        or ""
    ).strip()

    sql_id = str(
        source.get("sql_id", "")
        or ""
    ).strip()

    sql_text = str(
        source.get("sql", "")
        or ""
    ).strip()

    # 兼容旧来源格式
    if not workbook:
        citation_parts = re.split(
            r"[｜|]",
            citation,
        )

        workbook = (
            citation_parts[0].strip()
            if citation_parts
            else "未知来源"
        )

        workbook = Path(
            workbook
        ).name

    if not function_theme:
        function_theme = (
            extract_function_theme(
                source_text
            )
        )

    if not sql_id:
        sql_id = extract_sql_id(
            citation,
            source_text,
        )

    if not sql_text:
        sql_text = extract_sql_text(
            source_text
        )

    return {
        "workbook": (
            workbook or "未知来源"
        ),
        "function_theme": (
            function_theme or "未填写"
        ),
        "sql_id": (
            sql_id or "未知"
        ),
        "sql": sql_text,
    }