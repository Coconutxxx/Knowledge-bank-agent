from __future__ import annotations

import streamlit as st

from src.auth.auth_service import AuthenticatedUser
from src.services.export_service import ExportService


EXPORT_RESULT_KEY = "export_result"


def render_export_page(
    current_user: AuthenticatedUser,
) -> None:
    st.title("📥 下载 SQL 知识库")
    st.caption("从数据库生成最新的 SQL 知识库 Excel 文件")

    st.info(
        "导出的 SQL_ID 会按照数据库中的当前有效记录重新连续排列。"
        "隐藏的 record_id 用于以后再次导入时识别原数据库记录。"
    )

    if st.button(
        "生成最新版 Excel",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("正在从数据库生成 Excel 文件……"):
                service = ExportService()
                result = service.export_sql_records(current_user)

            st.session_state[EXPORT_RESULT_KEY] = {
                "file_name": result.file_name,
                "file_bytes": result.data,
                "record_count": result.record_count,
            }

        except Exception as exc:
            st.error(f"生成 Excel 文件失败：{exc}")
            return

    export_result = st.session_state.get(EXPORT_RESULT_KEY)

    if not export_result:
        return

    st.success(
        f"Excel 已生成，共导出 "
        f"{export_result['record_count']} 条 SQL 记录。"
    )

    st.download_button(
        label="下载 Excel 文件",
        data=export_result["file_bytes"],
        file_name=export_result["file_name"],
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True,
        type="primary",
    )