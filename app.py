"""Streamlit 图形界面。"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

from src.config import settings
from src.core.agent import KnowledgeAgent
from src.rag.document_loader import SUPPORTED_EXTENSIONS
from src.rag.indexer import KnowledgeIndexer
from src.rag.vector_store import SearchResult, VectorStore


# =========================================================
# 页面基本配置
# =========================================================

st.set_page_config(
    page_title="本地知识库 Agent",
    page_icon="📚",
    layout="wide",
)

st.title("📚 本地知识库问答 Agent")

st.caption(
    "上传文档 → 本地向量化 → Agent 主动检索 → 基于证据回答"
)


# =========================================================
# 初始化向量库和 Agent
# =========================================================

@st.cache_resource
def get_store() -> VectorStore:
    """创建并缓存向量数据库对象。"""

    return VectorStore()


def get_agent() -> KnowledgeAgent:
    """创建 Agent，并保存到当前会话中。"""

    if "agent" not in st.session_state:
        st.session_state.agent = KnowledgeAgent(
            store=get_store()
        )

    return st.session_state.agent


# =========================================================
# 上传文件保存
# =========================================================

def save_uploaded_file(uploaded_file) -> Path:
    """把用户上传的文件保存到 data/uploads。"""

    upload_dir = Path("data/uploads")
    upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 只保留文件名，避免文件路径问题
    safe_name = Path(uploaded_file.name).name

    destination = upload_dir / safe_name

    destination.write_bytes(
        uploaded_file.getbuffer()
    )

    return destination


# =========================================================
# 检索来源处理
# =========================================================

def extract_sql_text(text: str) -> str:
    """
    从结构化知识库文本中提取SQL正文。

    首选格式：
        SQL正文开始
        ...
        SQL正文结束

    兼容格式：
        SQL正文: ...
    """

    if not text:
        return ""

    # 第一种格式：SQL正文开始 / SQL正文结束
    sql_match = re.search(
        r"SQL正文开始\s*(.*?)\s*SQL正文结束",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if sql_match:
        return sql_match.group(1).strip()

    # 第二种格式：SQL正文:
    sql_match = re.search(
        r"SQL正文\s*[:：]\s*(.*)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if sql_match:
        return sql_match.group(1).strip()

    # 兼容旧索引
    return text.strip()


def extract_worksheet(location: str) -> str:
    """从 location 中提取工作表名称。"""

    if not location:
        return "未知工作表"

    match = re.search(
        r"工作表\s*[:：]\s*([^｜|]+)",
        location,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return location.strip()


def extract_sql_id(
    location: str,
    text: str,
) -> str:
    """从 location 或文本中提取 SQL_ID。"""

    location = location or ""
    text = text or ""

    # 优先从 location 中提取
    match = re.search(
        r"SQL[\s_-]*ID\s*[:：]\s*([^｜|\s]+)",
        location,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    # location 没有时，从正文中提取
    match = re.search(
        r"SQL[\s_-]*ID\s*[:：]\s*([^\n｜|]+)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return "未知"


def serialize_source(
    source: SearchResult,
) -> dict[str, str]:
    """
    把 SearchResult 转换成可以保存在
    st.session_state 中的普通字典。
    """

    source_text = source.text or ""
    source_location = source.location or ""
    source_name = source.source or "未知来源"

    return {
        "workbook": Path(source_name).name,
        "worksheet": extract_worksheet(
            source_location
        ),
        "sql_id": extract_sql_id(
            source_location,
            source_text,
        ),
        "sql": extract_sql_text(
            source_text
        ),
    }


def normalize_saved_source(
    source: dict,
) -> dict[str, str]:
    """
    兼容之前保存到对话中的旧来源格式。

    新格式：
        workbook
        worksheet
        sql_id
        sql

    旧格式：
        citation
        text
    """

    if "workbook" in source:
        return {
            "workbook": str(
                source.get(
                    "workbook",
                    "未知来源",
                )
            ),
            "worksheet": str(
                source.get(
                    "worksheet",
                    "未知工作表",
                )
            ),
            "sql_id": str(
                source.get(
                    "sql_id",
                    "未知",
                )
            ),
            "sql": str(
                source.get(
                    "sql",
                    "",
                )
            ),
        }

    # 兼容旧格式
    citation = str(
        source.get(
            "citation",
            "未知来源",
        )
    )

    source_text = str(
        source.get(
            "text",
            "",
        )
    )

    citation_parts = re.split(
        r"[｜|]",
        citation,
    )

    workbook = (
        citation_parts[0].strip()
        if citation_parts
        else "未知来源"
    )

    return {
        "workbook": workbook,
        "worksheet": extract_worksheet(
            citation
        ),
        "sql_id": extract_sql_id(
            citation,
            source_text,
        ),
        "sql": extract_sql_text(
            source_text
        ),
    }


def display_sources(
    sources: list[dict],
) -> None:
    """
    显示检索来源。

    只显示：
    1. 信息来源
    2. 工作表
    3. SQL_ID
    4. SQL语句
    """

    if not sources:
        return

    with st.expander("查看检索来源"):
        for number, original_source in enumerate(
            sources,
            start=1,
        ):
            source = normalize_saved_source(
                original_source
            )

            st.markdown(
                f"### 来源 {number}"
            )

            st.markdown(
                f"**信息来源：** "
                f"{source['workbook']}"
            )

            st.markdown(
                f"**工作表：** "
                f"{source['worksheet']}"
            )

            st.markdown(
                f"**SQL_ID：** "
                f"{source['sql_id']}"
            )

            sql_text = source["sql"].strip()

            if sql_text:
                st.markdown("**SQL语句：**")

                st.code(
                    sql_text,
                    language="sql",
                )
            else:
                st.caption(
                    "该来源没有识别到SQL正文。"
                )

            if number < len(sources):
                st.divider()


# =========================================================
# 初始化会话消息
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# 获取向量数据库
# =========================================================

store = get_store()


# =========================================================
# 左侧知识库管理区域
# =========================================================

with st.sidebar:
    st.header("知识库管理")

    st.metric(
        "已索引文本块",
        store.count(),
    )

    st.caption(
        f"聊天模型：{settings.model_name}"
    )

    st.caption(
        f"向量模型：{settings.embedding_model}"
    )

    supported_types = sorted(
        extension.lstrip(".")
        for extension in SUPPORTED_EXTENSIONS
    )

    uploaded_files = st.file_uploader(
        "上传资料",
        type=supported_types,
        accept_multiple_files=True,
        help=(
            "支持 PDF、Word、Excel、CSV、SQL、"
            "TXT、Markdown 等文件。"
        ),
    )

    import_button = st.button(
        "导入所选文件",
        type="primary",
        use_container_width=True,
    )

    if import_button:
        if not uploaded_files:
            st.warning("请先选择文件。")

        else:
            indexer = KnowledgeIndexer(store)

            total_files = 0
            total_sections = 0
            total_chunks = 0

            try:
                with st.spinner(
                    "正在读取、切分并向量化文档……"
                ):
                    for uploaded_file in uploaded_files:
                        saved_path = save_uploaded_file(
                            uploaded_file
                        )

                        ingest_result = indexer.ingest(
                            saved_path
                        )

                        total_files += int(
                            ingest_result.get(
                                "files",
                                0,
                            )
                        )

                        total_sections += int(
                            ingest_result.get(
                                "sections",
                                0,
                            )
                        )

                        total_chunks += int(
                            ingest_result.get(
                                "chunks",
                                0,
                            )
                        )

                if total_sections == 0:
                    st.error(
                        "文件已经保存，但没有识别到SQL记录。"
                        "请检查Excel标题行和文档读取代码。"
                    )

                else:
                    st.success(
                        f"已导入 {total_files} 个文件，"
                        f"{total_sections} 条SQL记录，"
                        f"{total_chunks} 个文本块。"
                    )

                    st.rerun()

            except Exception as exc:
                st.error(
                    f"导入失败：{exc}"
                )

    if st.button(
        "清空对话",
        use_container_width=True,
    ):
        get_agent().reset_memory()

        st.session_state.messages = []

        st.rerun()

    if st.button(
        "清空知识库",
        use_container_width=True,
    ):
        try:
            store.reset()

            get_agent().reset_memory()

            st.session_state.messages = []

            st.success(
                "知识库已经清空。"
            )

            st.rerun()

        except Exception as exc:
            st.error(
                f"清空知识库失败：{exc}"
            )


# =========================================================
# 显示历史对话
# =========================================================

for message in st.session_state.messages:
    role = message.get(
        "role",
        "assistant",
    )

    content = message.get(
        "content",
        "",
    )

    with st.chat_message(role):
        st.markdown(content)

        message_sources = message.get(
            "sources",
            [],
        )

        if message_sources:
            display_sources(
                message_sources
            )


# =========================================================
# 接收用户问题
# =========================================================

question = st.chat_input(
    "请输入你想查询的问题"
)


# =========================================================
# 执行知识库问答
# =========================================================

if question:
    # 保存用户问题
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # 显示用户问题
    with st.chat_message("user"):
        st.markdown(question)

    # 生成智能体回答
    with st.chat_message("assistant"):
        try:
            with st.spinner(
                "Agent 正在检索知识库并组织答案……"
            ):
                result = get_agent().run(
                    question
                )

            # 显示回答
            st.markdown(
                result.answer
            )

            # 在使用前先创建 serializable_sources
            serializable_sources = [
                serialize_source(source)
                for source in result.sources[:3]
            ]

            # 显示检索来源
            if serializable_sources:
                display_sources(
                    serializable_sources
                )

            # 显示 Agent 调用信息
            if result.trace:
                trace_details = [
                    str(item.get("detail", ""))
                    for item in result.trace
                    if item.get("detail")
                ]

                if trace_details:
                    st.caption(
                        "Agent 工具调用："
                        + " → ".join(
                            trace_details
                        )
                    )

            # 保存智能体回答和来源
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result.answer,
                    "sources": serializable_sources,
                }
            )

        except Exception as exc:
            error_message = (
                f"运行失败：{exc}"
            )

            st.error(
                error_message
            )

            # 同时把错误保存到对话记录，
            # 防止页面刷新后完全消失
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": error_message,
                    "sources": [],
                }
            )