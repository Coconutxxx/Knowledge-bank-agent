"""SQL 知识库 Agent 的 Streamlit 入口。"""

from __future__ import annotations

import streamlit as st

from src.auth.streamlit_auth import (
    get_current_user,
    logout_user,
    render_login_page,
)
from src.ui.chat_page import (
    render_chat_page,
)
from src.ui.export_page import (
    render_export_page,
)
from src.ui.knowledge_page import (
    render_knowledge_page,
)
from src.ui.user_management_page import (
    render_user_management_page,
)

st.set_page_config(
    page_title="SQL 知识库 Agent",
    page_icon="📚",
    layout="wide",
)


ROLE_LABELS = {
    "viewer": "只读用户",
    "editor": "编辑人员",
    "admin": "管理员",
}


current_user = get_current_user()

if current_user is None:
    render_login_page()
    st.stop()


with st.sidebar:
    st.header("系统导航")

    st.write(
        f"**当前用户：** "
        f"{current_user.username}"
    )

    st.write(
        f"**用户角色：** "
        f"{ROLE_LABELS.get(current_user.role, current_user.role)}"
    )

    st.divider()

    page_options = [
        "智能问答",
        "SQL 知识管理",
        "下载知识库",
    ]

    if current_user.role == "admin":
        page_options.append(
            "用户管理"
        )

    selected_page = st.radio(
        "请选择功能",
        options=page_options,
    )

    st.divider()

    st.caption(
        "数据库中的 SQL 记录是正式知识数据。"
        "普通问答通过向量索引检索这些记录。"
    )

    if st.button(
        "退出登录",
        use_container_width=True,
    ):
        logout_user()
        st.rerun()


if selected_page == "智能问答":
    render_chat_page()

elif selected_page == "SQL 知识管理":
    render_knowledge_page(
        current_user
    )

elif selected_page == "下载知识库":
    render_export_page(
        current_user
    )
    
elif selected_page == "用户管理":
    render_user_management_page(
        current_user
    )