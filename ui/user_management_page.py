"""管理员用户管理页面。"""

from __future__ import annotations

import streamlit as st

from src.auth.auth_service import (
    AuthenticatedUser,
)
from src.services.user_management_service import (
    ManagedUserView,
    UserManagementService,
)
from datetime import (
    datetime,
    timezone,
)
from zoneinfo import ZoneInfo

USER_FLASH_KEY = (
    "user_management_flash"
)

USER_FORM_REVISION_KEY = (
    "user_management_form_revision"
)

USER_TOAST_SHOWN_KEY = (
    "user_management_toast_shown"
)


ROLE_LABELS = {
    "viewer": "只读用户",
    "editor": "编辑人员",
    "admin": "管理员",
}

CHINA_TIMEZONE = ZoneInfo(
    "Asia/Shanghai"
)

def format_china_datetime(
    value: str | datetime | None,
) -> str:
    """
    将数据库UTC时间转换为中国时间。
    """

    if value is None:
        return "尚未登录"

    if isinstance(value, str):
        cleaned_value = value.strip()

        if not cleaned_value:
            return "尚未登录"

        cleaned_value = (
            cleaned_value.replace(
                "Z",
                "+00:00",
            )
        )

        try:
            value = datetime.fromisoformat(
                cleaned_value
            )

        except ValueError:
            return cleaned_value

    # SQLite可能返回没有时区信息的UTC时间
    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    china_time = value.astimezone(
        CHINA_TIMEZONE
    )

    return china_time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

def get_form_revision() -> int:
    return int(
        st.session_state.get(
            USER_FORM_REVISION_KEY,
            0,
        )
    )


def finish_user_operation(
    message: str,
) -> None:
    revision = (
        get_form_revision() + 1
    )

    st.session_state[
        USER_FORM_REVISION_KEY
    ] = revision

    st.session_state[
        USER_FLASH_KEY
    ] = {
        "id": revision,
        "type": "success",
        "content": message,
    }

    st.rerun()


def show_user_flash() -> None:
    message = st.session_state.get(
        USER_FLASH_KEY
    )

    if not message:
        return

    message_id = message.get(
        "id",
        0,
    )

    content = message.get(
        "content",
        "",
    )

    if (
        st.session_state.get(
            USER_TOAST_SHOWN_KEY
        )
        != message_id
    ):
        st.toast(
            content,
            icon="✅",
        )

        st.session_state[
            USER_TOAST_SHOWN_KEY
        ] = message_id

    message_col, close_col = (
        st.columns([8, 1])
    )

    with message_col:
        st.success(content)

    with close_col:
        if st.button(
            "关闭提示",
            key=(
                "close_user_flash_"
                f"{message_id}"
            ),
            use_container_width=True,
        ):
            st.session_state.pop(
                USER_FLASH_KEY,
                None,
            )

            st.session_state.pop(
                USER_TOAST_SHOWN_KEY,
                None,
            )

            st.rerun()


def user_label(
    user: ManagedUserView,
) -> str:
    status = (
        "启用"
        if user.is_active
        else "停用"
    )

    return (
        f"{user.username}"
        f"｜{ROLE_LABELS.get(user.role, user.role)}"
        f"｜{status}"
    )


def render_user_list(
    users: list[ManagedUserView],
) -> None:
    table_data = []

    for user in users:
        table_data.append(
            {
                "用户ID": user.id,
                "用户名": user.username,
                "角色": ROLE_LABELS.get(
                    user.role,
                    user.role,
                ),
                "状态": (
                    "启用"
                    if user.is_active
                    else "停用"
                ),
                "创建时间": (
                    format_china_datetime(
                        user.created_at
                    )
                ),
                "最后登录": (
                    format_china_datetime(
                        user.last_login_at
                    )
                ),
            }
        )

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
    )


def render_create_user(
    current_user: AuthenticatedUser,
    service: UserManagementService,
) -> None:
    revision = get_form_revision()

    st.subheader("创建普通用户")

    st.info(
        "新用户只能先创建为 viewer 或 editor。"
        "需要管理员权限时，可在“修改角色”中提升。"
    )

    with st.form(
        f"create_managed_user_{revision}",
        clear_on_submit=True,
    ):
        username = st.text_input(
            "用户名",
            placeholder=(
                "只能使用英文字母、数字、"
                "下划线、短横线和英文句点"
            ),
            key=f"new_username_{revision}",
        )

        role = st.selectbox(
            "初始角色",
            options=[
                "viewer",
                "editor",
            ],
            format_func=lambda value: (
                ROLE_LABELS[value]
            ),
            key=f"new_role_{revision}",
        )

        password = st.text_input(
            "初始密码",
            type="password",
            key=f"new_password_{revision}",
        )

        confirm_password = st.text_input(
            "确认密码",
            type="password",
            key=(
                f"confirm_new_password_"
                f"{revision}"
            ),
        )

        submitted = (
            st.form_submit_button(
                "创建用户",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    if password != confirm_password:
        st.error(
            "两次输入的密码不一致。"
        )
        return

    try:
        user = (
            service.create_managed_user(
                username=username,
                password=password,
                role=role,
                current_user=current_user,
            )
        )

        finish_user_operation(
            f"用户 {user.username!r} "
            "创建成功。"
        )

    except Exception as exc:
        st.error(
            f"创建用户失败：{exc}"
        )


def render_change_role(
    current_user: AuthenticatedUser,
    service: UserManagementService,
    users: list[ManagedUserView],
) -> None:
    revision = get_form_revision()

    user_by_id = {
        user.id: user
        for user in users
    }

    options = [
        None,
        *user_by_id.keys(),
    ]

    selected_user_id = st.selectbox(
        "选择需要修改角色的用户",
        options=options,
        format_func=lambda user_id: (
            "请选择用户"
            if user_id is None
            else user_label(
                user_by_id[user_id]
            )
        ),
        key=(
            f"role_user_id_{revision}"
        ),
    )

    if selected_user_id is None:
        st.info("请先选择用户。")
        return

    target_user = user_by_id[
        selected_user_id
    ]

    with st.form(
        (
            f"change_role_form_"
            f"{revision}"
        )
    ):
        st.write(
            f"当前角色："
            f"{ROLE_LABELS.get(target_user.role, target_user.role)}"
        )

        new_role = st.selectbox(
            "新角色",
            options=[
                "viewer",
                "editor",
                "admin",
            ],
            index=[
                "viewer",
                "editor",
                "admin",
            ].index(
                target_user.role
            ),
            format_func=lambda value: (
                ROLE_LABELS[value]
            ),
            key=f"target_role_{revision}",
        )

        submitted = (
            st.form_submit_button(
                "保存角色修改",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    try:
        user = service.change_role(
            target_user_id=(
                selected_user_id
            ),
            new_role=new_role,
            current_user=current_user,
        )

        finish_user_operation(
            f"用户 {user.username!r} "
            f"角色已修改为 "
            f"{ROLE_LABELS[user.role]}。"
        )

    except Exception as exc:
        st.error(
            f"修改角色失败：{exc}"
        )


def render_reset_password(
    current_user: AuthenticatedUser,
    service: UserManagementService,
    users: list[ManagedUserView],
) -> None:
    revision = get_form_revision()

    user_by_id = {
        user.id: user
        for user in users
    }

    selected_user_id = st.selectbox(
        "选择需要重置密码的用户",
        options=[
            None,
            *user_by_id.keys(),
        ],
        format_func=lambda user_id: (
            "请选择用户"
            if user_id is None
            else user_label(
                user_by_id[user_id]
            )
        ),
        key=(
            f"password_user_id_"
            f"{revision}"
        ),
    )

    if selected_user_id is None:
        st.info("请先选择用户。")
        return

    with st.form(
        (
            f"reset_password_form_"
            f"{revision}"
        ),
        clear_on_submit=True,
    ):
        new_password = st.text_input(
            "新密码",
            type="password",
            key=(
                f"reset_password_"
                f"{revision}"
            ),
        )

        confirm_password = st.text_input(
            "确认新密码",
            type="password",
            key=(
                f"confirm_reset_password_"
                f"{revision}"
            ),
        )

        submitted = (
            st.form_submit_button(
                "确认重置密码",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    if new_password != confirm_password:
        st.error(
            "两次输入的新密码不一致。"
        )
        return

    try:
        user = service.reset_password(
            target_user_id=(
                selected_user_id
            ),
            new_password=new_password,
            current_user=current_user,
        )

        finish_user_operation(
            f"用户 {user.username!r} "
            "密码重置成功。"
        )

    except Exception as exc:
        st.error(
            f"重置密码失败：{exc}"
        )


def render_active_status(
    current_user: AuthenticatedUser,
    service: UserManagementService,
    users: list[ManagedUserView],
) -> None:
    revision = get_form_revision()

    user_by_id = {
        user.id: user
        for user in users
    }

    selected_user_id = st.selectbox(
        "选择需要启用或停用的用户",
        options=[
            None,
            *user_by_id.keys(),
        ],
        format_func=lambda user_id: (
            "请选择用户"
            if user_id is None
            else user_label(
                user_by_id[user_id]
            )
        ),
        key=(
            f"active_user_id_{revision}"
        ),
    )

    if selected_user_id is None:
        st.info("请先选择用户。")
        return

    target_user = user_by_id[
        selected_user_id
    ]

    new_status = (
        not target_user.is_active
    )

    action_text = (
        "启用"
        if new_status
        else "停用"
    )

    with st.form(
        (
            f"active_status_form_"
            f"{revision}"
        )
    ):
        st.write(
            f"当前状态："
            f"{'启用' if target_user.is_active else '停用'}"
        )

        confirm = st.checkbox(
            f"我确认{action_text}用户 "
            f"{target_user.username!r}",
            key=(
                f"confirm_active_"
                f"{revision}"
            ),
        )

        submitted = (
            st.form_submit_button(
                f"确认{action_text}",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    if not confirm:
        st.warning(
            f"请先勾选{action_text}确认。"
        )
        return

    try:
        user = service.set_active(
            target_user_id=(
                selected_user_id
            ),
            is_active=new_status,
            current_user=current_user,
        )

        finish_user_operation(
            f"用户 {user.username!r} "
            f"已经{action_text}。"
        )

    except Exception as exc:
        st.error(
            f"{action_text}用户失败：{exc}"
        )

def render_delete_user(
    current_user: AuthenticatedUser,
    service: UserManagementService,
    users: list[ManagedUserView],
) -> None:
    """
    永久删除已经停用的用户。
    """

    revision = get_form_revision()

    disabled_users = [
        user
        for user in users
        if (
            not user.is_active
            and user.id
            != current_user.id
        )
    ]

    st.subheader("删除已停用用户")

    st.warning(
        "删除用户是永久操作，无法恢复。"
        "该用户创建的SQL和导入记录不会删除，"
        "但这些记录中的用户关联会被清除。"
    )

    if not disabled_users:
        st.info(
            "当前没有可以删除的已停用用户。"
        )
        return

    user_by_id = {
        user.id: user
        for user in disabled_users
    }

    selected_user_id = st.selectbox(
        "选择需要永久删除的用户",
        options=[
            None,
            *user_by_id.keys(),
        ],
        format_func=lambda user_id: (
            "请选择已停用用户"
            if user_id is None
            else user_label(
                user_by_id[user_id]
            )
        ),
        key=(
            f"delete_user_id_"
            f"{revision}"
        ),
    )

    if selected_user_id is None:
        st.info(
            "请先选择需要删除的用户。"
        )
        return

    target_user = user_by_id[
        selected_user_id
    ]

    with st.form(
        (
            f"delete_user_form_"
            f"{revision}"
        )
    ):
        st.write(
            f"即将删除用户："
            f"**{target_user.username}**"
        )

        confirmation_username = (
            st.text_input(
                "请输入该用户名以确认删除",
                placeholder=(
                    target_user.username
                ),
                key=(
                    f"delete_username_"
                    f"{revision}"
                ),
            )
        )

        confirm_delete = st.checkbox(
            "我确认永久删除该用户",
            key=(
                f"confirm_delete_user_"
                f"{revision}"
            ),
        )

        submitted = (
            st.form_submit_button(
                "永久删除用户",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    if (
        confirmation_username.strip()
        != target_user.username
    ):
        st.error(
            "输入的用户名不正确，"
            "删除操作已取消。"
        )
        return

    if not confirm_delete:
        st.warning(
            "请先勾选永久删除确认。"
        )
        return

    try:
        deleted_user = (
            service.delete_user(
                target_user_id=(
                    selected_user_id
                ),
                current_user=(
                    current_user
                ),
            )
        )

        finish_user_operation(
            f"用户 "
            f"{deleted_user.username!r} "
            "已永久删除。"
        )

    except Exception as exc:
        st.error(
            f"删除用户失败：{exc}"
        )

def render_user_management_page(
    current_user: AuthenticatedUser,
) -> None:
    st.title("👥 用户管理")
    st.caption(
        "创建用户、调整角色、重置密码以及管理账号状态"
    )

    if current_user.role != "admin":
        st.error(
            "只有管理员可以访问用户管理页面。"
        )
        return

    show_user_flash()

    service = UserManagementService()

    try:
        users = service.list_users(
            current_user
        )

    except Exception as exc:
        st.error(
            f"读取用户列表失败：{exc}"
        )
        return

    active_count = sum(
        1
        for user in users
        if user.is_active
    )

    admin_count = sum(
        1
        for user in users
        if (
            user.is_active
            and user.role == "admin"
        )
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "用户总数",
            len(users),
        )

    with col2:
        st.metric(
            "有效用户",
            active_count,
        )

    with col3:
        st.metric(
            "有效管理员",
            admin_count,
        )

    tabs = st.tabs(
        [
            "用户列表",
            "创建用户",
            "修改角色",
            "重置密码",
            "启用/停用",
            "删除用户",
        ]
    )

    with tabs[0]:
        render_user_list(
            users
        )

    with tabs[1]:
        render_create_user(
            current_user,
            service,
        )

    with tabs[2]:
        render_change_role(
            current_user,
            service,
            users,
        )

    with tabs[3]:
        render_reset_password(
            current_user,
            service,
            users,
        )

    with tabs[4]:
        render_active_status(
            current_user,
            service,
            users,
        )
    with tabs[5]:
        render_delete_user(
            current_user,
            service,
            users,
        )