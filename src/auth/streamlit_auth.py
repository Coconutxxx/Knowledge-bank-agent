from __future__ import annotations

import time

import streamlit as st

from src.auth.auth_service import (
    AuthenticatedUser,
    authenticate_user,
    get_user_by_id,
)
from src.config import settings


AUTH_USER_ID_KEY = "auth_user_id"
AUTH_LAST_ACTIVITY_KEY = "auth_last_activity"


def clear_login_state() -> None:
    """
    清除当前浏览器会话中的登录信息和用户相关缓存。
    不会删除数据库、向量库或知识库文件。
    """
    keys_to_clear = [
        AUTH_USER_ID_KEY,
        AUTH_LAST_ACTIVITY_KEY,
        "messages",
        "knowledge_agent",
        "export_result",
        "import_preview",
    ]

    for key in keys_to_clear:
        st.session_state.pop(key, None)


def login_user(
    username: str,
    password: str,
) -> AuthenticatedUser | None:
    """
    校验用户名和密码。

    登录成功：
        将用户ID和最后活动时间写入 session_state。

    登录失败：
        返回 None。
    """
    user = authenticate_user(
        username=username.strip(),
        password=password,
    )

    if user is None:
        return None

    st.session_state[AUTH_USER_ID_KEY] = user.id
    st.session_state[AUTH_LAST_ACTIVITY_KEY] = time.time()

    return user


def get_current_user() -> AuthenticatedUser | None:
    """
    获取当前登录用户，并检查会话是否超时。

    SESSION_TIMEOUT_MINUTES 表示连续无操作多少分钟后退出登录。
    """
    user_id = st.session_state.get(AUTH_USER_ID_KEY)
    last_activity = st.session_state.get(AUTH_LAST_ACTIVITY_KEY)

    if user_id is None or last_activity is None:
        return None

    timeout_seconds = settings.session_timeout_minutes * 60
    elapsed_seconds = time.time() - float(last_activity)

    if elapsed_seconds > timeout_seconds:
        clear_login_state()
        return None

    user = get_user_by_id(int(user_id))

    if user is None:
        clear_login_state()
        return None

    if not user.is_active:
        clear_login_state()
        return None

    # 当前请求有效，刷新最后活动时间
    st.session_state[AUTH_LAST_ACTIVITY_KEY] = time.time()

    return user


def logout_user() -> None:
    """
    退出当前用户。
    """
    clear_login_state()


def render_login_page() -> None:
    """
    显示登录页面。
    """
    st.title("📚 SQL 知识库 Agent")
    st.caption("请先登录后再使用知识库问答和管理功能")

    left_column, center_column, right_column = st.columns([1, 1.2, 1])

    with center_column:
        with st.form("login_form", clear_on_submit=False):
            st.subheader("用户登录")

            username = st.text_input(
                "用户名",
                placeholder="请输入用户名",
            )

            password = st.text_input(
                "密码",
                type="password",
                placeholder="请输入密码",
            )

            submitted = st.form_submit_button(
                "登录",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not username.strip():
                st.warning("请输入用户名。")
                return

            if not password:
                st.warning("请输入密码。")
                return

            user = login_user(
                username=username,
                password=password,
            )

            if user is None:
                st.error("用户名或密码错误，或者该用户已被停用。")
                return

            st.success(f"登录成功，欢迎 {user.username}。")
            st.rerun()