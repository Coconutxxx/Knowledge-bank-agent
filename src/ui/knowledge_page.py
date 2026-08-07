from __future__ import annotations

import streamlit as st

from src.auth.auth_service import (
    AuthenticatedUser,
    user_has_role,
)
from src.services.knowledge_service import (
    KnowledgeService,
    SQLRecordData,
    SQLRecordView,
)
from src.services.vector_sync_service import (
    VectorSyncService,
)

FLASH_KEY = "knowledge_page_flash"
FORM_REVISION_KEY = "knowledge_form_revision"
TOAST_SHOWN_KEY = "knowledge_toast_shown"

def safe_text(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()

def get_form_revision() -> int:
    """
    获取当前表单版本。

    每次操作成功后版本加一，
    Streamlit会把它识别为一套新组件，
    从而清空之前填写的内容。
    """

    return int(
        st.session_state.get(
            FORM_REVISION_KEY,
            0,
        )
    )

def increase_form_revision() -> int:
    """
    增加表单版本并返回新版本号。
    """

    new_revision = (
        get_form_revision() + 1
    )

    st.session_state[
        FORM_REVISION_KEY
    ] = new_revision

    return new_revision

@st.cache_resource
def get_vector_sync_service() -> VectorSyncService:
    """
    缓存向量同步服务，避免每次页面刷新
    都重新加载本地向量模型。
    """

    return VectorSyncService()

def show_flash_message() -> None:
    """
    显示最近一次操作结果。

    同时使用：
    1. 页面固定成功提示；
    2. 右下角Toast提示。

    即使用户停留在页面底部，也能看到结果。
    """

    message = st.session_state.get(
        FLASH_KEY
    )

    if not message:
        return

    message_id = message.get(
        "id",
        0,
    )

    message_type = message.get(
        "type",
        "success",
    )

    content = message.get(
        "content",
        "",
    )

    # 每条操作结果只弹出一次Toast
    if (
        st.session_state.get(
            TOAST_SHOWN_KEY
        )
        != message_id
    ):
        if message_type == "success":
            st.toast(
                content,
                icon="✅",
            )

        elif message_type == "warning":
            st.toast(
                content,
                icon="⚠️",
            )

        else:
            st.toast(
                content,
                icon="❌",
            )

        st.session_state[
            TOAST_SHOWN_KEY
        ] = message_id

    message_col, close_col = st.columns(
        [8, 1]
    )

    with message_col:
        if message_type == "warning":
            st.warning(content)

        elif message_type == "error":
            st.error(content)

        else:
            st.success(content)

    with close_col:
        if st.button(
            "关闭提示",
            key=(
                f"close_knowledge_flash_"
                f"{message_id}"
            ),
            use_container_width=True,
        ):
            st.session_state.pop(
                FLASH_KEY,
                None,
            )

            st.session_state.pop(
                TOAST_SHOWN_KEY,
                None,
            )

            st.rerun()

def finish_database_change(
    success_message: str,
) -> None:
    """
    数据库修改成功后：

    1. 同步向量库；
    2. 保存成功提示；
    3. 更新表单版本；
    4. 刷新页面。
    """

    # 每次成功操作生成新的版本号
    operation_id = (
        increase_form_revision()
    )

    try:
        result = (
            get_vector_sync_service()
            .process_pending(limit=1000)
        )

        success_count = int(
            result.get(
                "success",
                0,
            )
        )

        failed_count = int(
            result.get(
                "failed",
                0,
            )
        )

        if failed_count > 0:
            st.session_state[FLASH_KEY] = {
                "id": operation_id,
                "type": "warning",
                "content": (
                    f"{success_message}"
                    f"数据库操作已经成功；"
                    f"向量同步成功 "
                    f"{success_count} 条，"
                    f"失败 {failed_count} 条。"
                ),
            }

        else:
            st.session_state[FLASH_KEY] = {
                "id": operation_id,
                "type": "success",
                "content": (
                    f"{success_message}"
                    f"向量库同步成功 "
                    f"{success_count} 条。"
                ),
            }

    except Exception as exc:
        # 数据库操作已经成功，
        # 所以这里是warning而不是error
        st.session_state[FLASH_KEY] = {
            "id": operation_id,
            "type": "warning",
            "content": (
                f"{success_message}"
                "数据库操作已经成功，"
                f"但向量同步出现异常：{exc}"
            ),
        }

    st.rerun()

def render_record_form(
    prefix: str,
    record: SQLRecordView | None = None,
) -> SQLRecordData:
    """
    显示新增或编辑表单，并返回 SQLRecordData。
    """

    function_theme = st.text_input(
        "功能主题 *",
        value=(
            safe_text(record.function_theme)
            if record
            else ""
        ),
        key=f"{prefix}_function_theme",
        placeholder="例如：查询号码余额/充值金额",
    )

    business_domain = st.text_input(
        "业务域",
        value=(
            safe_text(record.business_domain)
            if record
            else ""
        ),
        key=f"{prefix}_business_domain",
        placeholder="例如：移动、宽带、收入",
    )

    col1, col2 = st.columns(2)

    with col1:
        step = st.text_input(
            "步骤",
            value=(
                safe_text(record.step)
                if record
                else ""
            ),
            key=f"{prefix}_step",
        )

        function_type = st.text_input(
            "功能类型",
            value=(
                safe_text(record.function_type)
                if record
                else ""
            ),
            key=f"{prefix}_function_type",
        )

        source_tables = st.text_area(
            "涉及来源表",
            value=(
                safe_text(record.source_tables)
                if record
                else ""
            ),
            key=f"{prefix}_source_tables",
            height=100,
        )

    with col2:
        statement_type = st.text_input(
            "语句类型",
            value=(
                safe_text(record.statement_type)
                if record
                else ""
            ),
            key=f"{prefix}_statement_type",
            placeholder="例如：查询、建表、插入",
        )

        table_completeness = st.text_input(
            "表资料完整性",
            value=(
                safe_text(
                    record.table_completeness
                )
                if record
                else ""
            ),
            key=f"{prefix}_table_completeness",
        )

        field_completeness = st.text_input(
            "字段资料完整性",
            value=(
                safe_text(
                    record.field_completeness
                )
                if record
                else ""
            ),
            key=f"{prefix}_field_completeness",
        )

    sql_text = st.text_area(
        "SQL 正文 *",
        value=(
            record.sql_text
            if record
            else ""
        ),
        key=f"{prefix}_sql_text",
        height=360,
        placeholder="请输入完整的 SQL 语句",
    )

    notes = st.text_area(
        "备注",
        value=(
            safe_text(record.notes)
            if record
            else ""
        ),
        key=f"{prefix}_notes",
        height=100,
    )

    st.markdown("#### 来源信息")

    source_col1, source_col2 = st.columns(2)

    with source_col1:
        source_file = st.text_input(
            "来源文件",
            value=(
                safe_text(record.source_file)
                if record
                else "系统手工新增"
            ),
            key=f"{prefix}_source_file",
        )

        source_sql_id = st.text_input(
            "原始文件 SQL_ID",
            value=(
                safe_text(
                    record.source_sql_id
                )
                if record
                else ""
            ),
            key=f"{prefix}_source_sql_id",
            help=(
                "这是记录在原始文件中的编号，"
                "不是数据库动态 SQL_ID。"
            ),
        )

    with source_col2:
        source_sheet = st.text_input(
            "来源工作表",
            value=(
                safe_text(record.source_sheet)
                if record
                else "SQL知识表"
            ),
            key=f"{prefix}_source_sheet",
        )

        source_row = st.number_input(
            "原始文件行号",
            min_value=0,
            step=1,
            value=(
                int(record.source_row or 0)
                if record
                else 0
            ),
            key=f"{prefix}_source_row",
            help="填写0表示没有原始行号。",
        )

    with st.expander("内部检查信息"):
        missing_tables = st.text_area(
            "缺失表",
            value=(
                safe_text(record.missing_tables)
                if record
                else ""
            ),
            key=f"{prefix}_missing_tables",
        )

        unregistered_fields = st.text_area(
            "未登记字段",
            value=(
                safe_text(
                    record.unregistered_fields
                )
                if record
                else ""
            ),
            key=f"{prefix}_unregistered_fields",
        )

        field_ownership_unknown = st.text_area(
            "归属不明确字段",
            value=(
                safe_text(
                    record.field_ownership_unknown
                )
                if record
                else ""
            ),
            key=(
                f"{prefix}_field_ownership_unknown"
            ),
        )

        unexplained_fields = st.text_area(
            "未解释字段",
            value=(
                safe_text(
                    record.unexplained_fields
                )
                if record
                else ""
            ),
            key=f"{prefix}_unexplained_fields",
        )

    return SQLRecordData(
        function_theme=function_theme,
        sql_text=sql_text,
        source_sql_id=(
            source_sql_id or None
        ),
        source_row=(
            int(source_row)
            if source_row > 0
            else None
        ),
        business_domain=(
            business_domain or None
        ),
        step=step or None,
        function_type=(
            function_type or None
        ),
        statement_type=(
            statement_type or None
        ),
        source_tables=(
            source_tables or None
        ),
        table_completeness=(
            table_completeness or None
        ),
        field_completeness=(
            field_completeness or None
        ),
        missing_tables=(
            missing_tables or None
        ),
        unregistered_fields=(
            unregistered_fields or None
        ),
        field_ownership_unknown=(
            field_ownership_unknown or None
        ),
        unexplained_fields=(
            unexplained_fields or None
        ),
        notes=notes or None,
        source_file=source_file or None,
        source_sheet=source_sheet or None,
    )


def render_view_tab(
    records: list[SQLRecordView],
) -> None:
    if not records:
        st.info("没有找到符合条件的 SQL 记录。")
        return

    table_data: list[dict[str, object]] = []

    for record in records:
        table_data.append(
            {
                "SQL_ID": (
                    record.sql_id
                    if record.sql_id is not None
                    else "已删除"
                ),
                "业务域": safe_text(
                    record.business_domain
                ),
                "功能主题": record.function_theme,
                "语句类型": safe_text(
                    record.statement_type
                ),
                "来源文件": safe_text(
                    record.source_file
                ),
                "来源工作表": safe_text(
                    record.source_sheet
                ),
                "版本": record.version,
                "状态": (
                    "已删除"
                    if record.deleted_at
                    else "有效"
                ),
            }
        )

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("SQL 详情")

    record_by_id = {
        record.id: record
        for record in records
    }

    selected_record_id = st.selectbox(
        "选择一条 SQL 记录",
        options=list(record_by_id.keys()),
        format_func=lambda record_id: (
            (
                f"SQL_ID "
                f"{record_by_id[record_id].sql_id}"
            )
            if (
                record_by_id[record_id].sql_id
                is not None
            )
            else "已删除记录"
        )
        + "｜"
        + record_by_id[record_id].function_theme,
        key="view_record_id",
    )

    record = record_by_id[
        selected_record_id
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.write(
            f"**SQL_ID：** "
            f"{record.sql_id or '已删除'}"
        )
        st.write(
            f"**功能主题：** "
            f"{record.function_theme}"
        )
        st.write(
            f"**业务域：** "
            f"{safe_text(record.business_domain) or '未填写'}"
        )
        st.write(
            f"**功能类型：** "
            f"{safe_text(record.function_type) or '未填写'}"
        )

    with col2:
        st.write(
            f"**来源文件：** "
            f"{safe_text(record.source_file) or '未填写'}"
        )
        st.write(
            f"**来源工作表：** "
            f"{safe_text(record.source_sheet) or '未填写'}"
        )
        st.write(
            f"**原始 SQL_ID：** "
            f"{safe_text(record.source_sql_id) or '未填写'}"
        )
        st.write(
            f"**当前版本：** {record.version}"
        )

    if safe_text(record.source_tables):
        st.write("**涉及来源表：**")
        st.write(record.source_tables)

    if safe_text(record.notes):
        st.write("**备注：**")
        st.write(record.notes)

    st.write("**SQL 正文：**")

    st.code(
        record.sql_text,
        language="sql",
    )


def render_create_tab(
    current_user: AuthenticatedUser,
    service: KnowledgeService,
) -> None:
    st.subheader("新增 SQL 记录")

    st.info(
        "系统会自动把新记录的 SQL_ID "
        "追加到当前最大序号之后。"
    )

    form_revision = (
        get_form_revision()
    )
    with st.form(
        (
            "create_sql_record_form_"
            f"{form_revision}"
        ),
        clear_on_submit=True,
    ):
        data = render_record_form(
            prefix=(
                f"create_{form_revision}"
            ),
        )

        submitted = st.form_submit_button(
            "确认新增",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    try:
        created_record = service.create_record(
            data=data,
            current_user=current_user,
        )

        finish_database_change(
            f"SQL_ID {created_record.sql_id} "
            "新增成功。"
        )

    except Exception as exc:
        st.error(f"新增失败：{exc}")

def render_edit_tab(
    current_user: AuthenticatedUser,
    service: KnowledgeService,
    records: list[SQLRecordView],
) -> None:
    """
    修改SQL记录。

    修改成功后：
    1. 增加表单版本；
    2. 刷新页面；
    3. 清空当前选择；
    4. 隐藏旧编辑表单；
    5. 重新从数据库读取记录。
    """

    active_records = [
        record
        for record in records
        if record.deleted_at is None
    ]

    if not active_records:
        st.info(
            "当前没有可以修改的记录。"
        )
        return

    record_by_id = {
        record.id: record
        for record in active_records
    }

    form_revision = (
        get_form_revision()
    )

    # 增加None作为默认选项。
    # 修改成功且版本变化后，会重新回到None。
    record_options = [
        None,
        *record_by_id.keys(),
    ]

    selected_record_id = st.selectbox(
        "选择需要修改的 SQL 记录",
        options=record_options,
        format_func=lambda record_id: (
            "请选择需要修改的记录"
            if record_id is None
            else (
                f"SQL_ID "
                f"{record_by_id[record_id].sql_id}"
                f"｜"
                f"{record_by_id[record_id].function_theme}"
            )
        ),
        index=0,
        key=(
            "edit_record_id_"
            f"{form_revision}"
        ),
    )

    # 没有选择记录时，不显示编辑表单
    if selected_record_id is None:
        st.info(
            "请先在上方选择一条需要修改的 SQL 记录。"
        )
        return

    selected_record = record_by_id[
        selected_record_id
    ]

    st.caption(
        f"数据库内部 record_id："
        f"{selected_record.id}；"
        f"当前 SQL_ID："
        f"{selected_record.sql_id}；"
        f"版本：{selected_record.version}"
    )

    form_key = (
        "edit_sql_record_form_"
        f"{selected_record.id}_"
        f"{form_revision}"
    )

    with st.form(
        form_key,
        clear_on_submit=True,
    ):
        data = render_record_form(
            prefix=(
                f"edit_"
                f"{selected_record.id}_"
                f"{form_revision}"
            ),
            record=selected_record,
        )

        submitted = (
            st.form_submit_button(
                "保存修改",
                type="primary",
                use_container_width=True,
            )
        )

    if not submitted:
        return

    try:
        updated_record = (
            service.update_record(
                record_id=(
                    selected_record.id
                ),
                data=data,
                expected_version=(
                    selected_record.version
                ),
                current_user=current_user,
            )
        )

        # 这里会：
        # 1. 同步向量库
        # 2. 增加表单版本
        # 3. 保存成功提示
        # 4. 执行st.rerun()
        finish_database_change(
            f"SQL_ID "
            f"{updated_record.sql_id} "
            "修改成功。"
        )

    except Exception as exc:
        st.error(
            f"修改失败：{exc}"
        )

def render_delete_restore_tab(
    current_user: AuthenticatedUser,
    service: KnowledgeService,
) -> None:
    try:
        all_records = service.list_records(
            current_user=current_user,
            include_deleted=True,
            limit=1000,
        )

    except Exception as exc:
        st.error(f"读取记录失败：{exc}")
        return

    active_records = [
        record
        for record in all_records
        if record.deleted_at is None
    ]

    deleted_records = [
        record
        for record in all_records
        if record.deleted_at is not None
    ]

    st.subheader("删除有效记录")

    st.warning(
        "删除后，该记录会被软删除，"
        "后续 SQL_ID 会自动向前移动。"
    )

    if active_records:
        form_revision = (
            get_form_revision()
        )
        active_by_id = {
            record.id: record
            for record in active_records
        }

        with st.form(
            (
                "delete_record_form_"
                f"{form_revision}"
            )
        ):
            delete_record_id = st.selectbox(
                "选择需要删除的记录",
                options=list(
                    active_by_id.keys()
                ),
                format_func=lambda record_id: (
                    f"SQL_ID "
                    f"{active_by_id[record_id].sql_id}"
                    f"｜"
                    f"{active_by_id[record_id].function_theme}"
                ),
                key=(
                    "delete_record_id_"
                    f"{form_revision}"
                ),
            )

            confirm_delete = st.checkbox(
                "我确认删除该记录并重新排列后续 SQL_ID",
                key=(
                    "confirm_delete_"
                    f"{form_revision}"),
            )

            delete_submitted = (
                st.form_submit_button(
                    "确认删除",
                    type="primary",
                    use_container_width=True,
                )
            )

        if delete_submitted:
            if not confirm_delete:
                st.warning(
                    "请先勾选删除确认。"
                )

            else:
                try:
                    original_record = active_by_id[
                        delete_record_id
                    ]

                    original_sql_id = (
                        original_record.sql_id
                    )

                    service.delete_record(
                        record_id=delete_record_id,
                        current_user=current_user,
                    )

                    finish_database_change(
                        f"SQL_ID {original_sql_id} 删除成功，"
                        "后续 SQL_ID 已重新排列。"
                    )

                except Exception as exc:
                    st.error(
                        f"删除失败：{exc}"
                    )

                except Exception as exc:
                    st.error(
                        f"删除失败：{exc}"
                    )

    else:
        st.info("当前没有可删除的有效记录。")

    st.divider()
    st.subheader("恢复已删除记录")

    st.caption(
        "恢复后的记录会追加到当前最大 SQL_ID 之后，"
        "不会恢复到原来的序号位置。"
    )

    if not deleted_records:
        st.info("当前没有已删除记录。")
        return

    deleted_by_id = {
        record.id: record
        for record in deleted_records
    }

    with st.form(
            (
                "restore_record_form_"
                f"{form_revision}"
            )
        ):
        restore_record_id = st.selectbox(
            "选择需要恢复的记录",
            options=list(
                deleted_by_id.keys()
            ),
            format_func=lambda record_id: (
                f"record_id "
                f"{deleted_by_id[record_id].id}"
                f"｜"
                f"{deleted_by_id[record_id].function_theme}"
            ),
            key=(
                "restore_record_id_"
                f"{form_revision}"
            ),
        )

        restore_submitted = (
            st.form_submit_button(
                "恢复记录",
                use_container_width=True,
            )
        )

    if restore_submitted:
        try:
            restored_record = (
                service.restore_record(
                    record_id=restore_record_id,
                    current_user=current_user,
                )
            )

            finish_database_change(
                f"记录恢复成功，新 SQL_ID 为 "
                f"{restored_record.sql_id}。"
            )

        except Exception as exc:
            st.error(f"恢复失败：{exc}")


def render_knowledge_page(
    current_user: AuthenticatedUser,
) -> None:
    st.title("🗂️ SQL 知识库管理")
    st.caption(
        "数据库是 SQL 知识的主数据源，"
        "增删改后会同步更新向量索引。"
    )

    show_flash_message()

    service = KnowledgeService()

    can_edit = user_has_role(
        current_user,
        "editor",
        "admin",
    )

    is_admin = user_has_role(
        current_user,
        "admin",
    )

    try:
        total_count = (
            service.count_active_records(
                current_user=current_user,
            )
        )

    except Exception as exc:
        st.error(
            f"读取知识库记录数量失败：{exc}"
        )
        return

    metric_col1, metric_col2, metric_col3 = (
        st.columns(3)
    )

    with metric_col1:
        st.metric(
            "有效 SQL 记录",
            total_count,
        )

    with metric_col2:
        st.metric(
            "当前用户",
            current_user.username,
        )

    with metric_col3:
        st.metric(
            "当前角色",
            current_user.role,
        )

    if is_admin:
        if st.button(
            "重试失败的向量同步任务",
        ):
            try:
                sync_service = (
                    get_vector_sync_service()
                )

                retry_count = (
                    sync_service.retry_failed()
                )

                sync_result = (
                    sync_service.process_pending(
                        limit=1000
                    )
                )

                st.success(
                    f"重新放回队列 {retry_count} 条，"
                    f"同步成功 "
                    f"{sync_result['success']} 条，"
                    f"失败 "
                    f"{sync_result['failed']} 条。"
                )

            except Exception as exc:
                st.error(
                    f"向量同步失败：{exc}"
                )

    st.divider()

    search_col1, search_col2 = st.columns(
        [4, 1]
    )

    with search_col1:
        keyword = st.text_input(
            "搜索知识库",
            placeholder=(
                "请输入功能主题、业务域、"
                "SQL_ID、来源表或SQL关键词"
            ),
        )

    with search_col2:
        include_deleted = False

        if is_admin:
            include_deleted = st.checkbox(
                "包含已删除",
                value=False,
            )

    try:
        records = service.list_records(
            current_user=current_user,
            keyword=keyword.strip(),
            include_deleted=include_deleted,
            limit=1000,
        )

    except Exception as exc:
        st.error(
            f"读取 SQL 知识记录失败：{exc}"
        )
        return

    tab_names = ["查看"]

    if can_edit:
        tab_names.extend(
            [
                "新增",
                "修改",
            ]
        )

    if is_admin:
        tab_names.append(
            "删除/恢复"
        )

    tab_objects = st.tabs(
        tab_names
    )

    tabs = dict(
        zip(
            tab_names,
            tab_objects,
        )
    )

    with tabs["查看"]:
        render_view_tab(
            records
        )

    if can_edit:
        with tabs["新增"]:
            render_create_tab(
                current_user,
                service,
            )

        with tabs["修改"]:
            render_edit_tab(
                current_user,
                service,
                records,
            )

    if is_admin:
        with tabs["删除/恢复"]:
            render_delete_restore_tab(
                current_user,
                service,
            )