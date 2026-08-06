"""把SQL知识Excel导入关系数据库。"""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

from src.auth.auth_service import (
    authenticate_user,
)
from src.config import settings
from src.services.import_service import (
    ImportService,
)
from src.services.vector_sync_service import (
    VectorSyncService,
)


def display_candidate(
    candidate,
    action: str,
) -> None:
    """显示一条待导入记录。"""

    source_sql_id = (
        candidate.data.source_sql_id
        or "未提供"
    )

    print(
        f"- 操作={action}，"
        f"原文件SQL_ID={source_sql_id}，"
        f"Excel行={candidate.row_number}，"
        f"功能={candidate.data.function_theme}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "把SQL知识Excel导入关系数据库"
        ),
    )

    parser.add_argument(
        "--file",
        required=True,
        help="需要导入的xlsx文件路径",
    )

    arguments = parser.parse_args()

    file_path = Path(
        arguments.file
    )

    if not file_path.exists():
        raise FileNotFoundError(
            f"文件不存在：{file_path}"
        )

    if file_path.name.startswith("~$"):
        raise ValueError(
            "不能导入Excel临时文件。"
            "请关闭Excel后选择不以~$开头的文件。"
        )

    print(
        "当前Chroma集合：",
        settings.collection_name,
    )

    print(
        "准备导入文件：",
        file_path,
    )

    username = input(
        "管理员或编辑人员用户名："
    ).strip()

    password = getpass(
        "密码："
    )

    current_user = authenticate_user(
        username,
        password,
    )

    if current_user is None:
        print("登录失败。")
        return

    if current_user.role not in {
        "editor",
        "admin",
    }:
        print(
            "当前账号没有导入权限。"
        )
        return

    import_service = ImportService()

    print(
        "\n正在解析并比较Excel……"
    )

    preview = import_service.preview(
        path=file_path,
        current_user=current_user,
    )

    print(
        "\n========== 导入预览 =========="
    )

    print(
        f"导入模式：{preview.mode}"
    )

    print(
        f"总记录数：{preview.total_count}"
    )

    print(
        f"准备新增：{len(preview.inserts)}"
    )

    print(
        f"准备更新：{len(preview.updates)}"
    )

    print(
        f"内容相同：{len(preview.unchanged)}"
    )

    print(
        f"无效记录：{len(preview.invalid)}"
    )

    if preview.mode == "append":
        print(
            "说明：该文件没有系统记录ID，"
            "有效记录将按Excel顺序追加，"
            "数据库会自动重新分配SQL_ID。"
        )

    elif preview.mode == "update":
        print(
            "说明：该文件包含系统记录ID，"
            "系统将根据记录ID更新已有记录。"
        )

    if preview.inserts:
        print(
            "\n新增记录示例："
        )

        for candidate in preview.inserts[:10]:
            display_candidate(
                candidate,
                "新增",
            )

        if len(preview.inserts) > 10:
            print(
                f"...其余 "
                f"{len(preview.inserts) - 10} "
                "条新增记录未展示"
            )

    if preview.updates:
        print(
            "\n更新记录示例："
        )

        for candidate in preview.updates[:10]:
            display_candidate(
                candidate,
                "更新",
            )

        if len(preview.updates) > 10:
            print(
                f"...其余 "
                f"{len(preview.updates) - 10} "
                "条更新记录未展示"
            )

    if preview.unchanged:
        print(
            "\n内容相同记录示例："
        )

        for candidate in preview.unchanged[:5]:
            display_candidate(
                candidate,
                "跳过",
            )

    if preview.invalid:
        print(
            "\n无效记录："
        )

        for item in preview.invalid[:20]:
            print(
                f"- 工作表="
                f"{item.get('sheet', '未知')}，"
                f"行="
                f"{item.get('row', '未知')}，"
                f"原文件SQL_ID="
                f"{item.get('sql_id', '') or '未提供'}，"
                f"原因="
                f"{item.get('reason', '未知原因')}"
            )

        if len(preview.invalid) > 20:
            print(
                f"...其余 "
                f"{len(preview.invalid) - 20} "
                "条无效记录未展示"
            )

    # 如果没有任何可以新增或更新的内容
    if (
        not preview.inserts
        and not preview.updates
    ):
        print(
            "\n当前文件没有需要新增或更新的记录。"
        )

        if preview.unchanged:
            print(
                "所有有效记录均与数据库一致。"
            )

        return

    print(
        "\n注意："
        "无效记录不会进入数据库。"
    )

    if preview.mode == "append":
        print(
            "本次有效新增记录将从数据库"
            "当前最大SQL_ID之后连续编号。"
        )

    confirm = input(
        "\n确认执行导入吗？"
        "输入 yes 继续："
    ).strip().lower()

    if confirm != "yes":
        print("已取消导入。")
        return

    print(
        "\n正在写入数据库……"
    )

    result = import_service.apply(
        preview=preview,
        current_user=current_user,
    )

    print(
        "\n========== 数据库导入结果 =========="
    )

    print(
        f"批次ID：{result['batch_id']}"
    )

    print(
        f"状态：{result['status']}"
    )

    print(
        f"新增：{result['inserted']}"
    )

    print(
        f"更新：{result['updated']}"
    )

    print(
        f"未变化：{result['unchanged']}"
    )

    print(
        f"无效：{result['invalid']}"
    )

    print(
        f"失败：{result['failed']}"
    )

    failed_items = result.get(
        "failed_items",
        [],
    )

    if failed_items:
        print(
            "\n失败明细："
        )

        for item in failed_items:
            print(
                f"- Excel行="
                f"{item.get('row', '未知')}，"
                f"操作="
                f"{item.get('action', '未知')}，"
                f"错误="
                f"{item.get('error', '未知错误')}"
            )

    if (
        result["inserted"] == 0
        and result["updated"] == 0
    ):
        print(
            "\n没有成功写入记录，"
            "本次不执行向量同步。"
        )
        return

    print(
        "\n正在同步Chroma向量库……"
    )

    sync_service = (
        VectorSyncService()
    )

    sync_result = (
        sync_service.process_pending(
            limit=1000
        )
    )

    print(
        "\n========== 向量同步结果 =========="
    )

    print(
        f"待处理：{sync_result['total']}"
    )

    print(
        f"成功：{sync_result['success']}"
    )

    print(
        f"失败：{sync_result['failed']}"
    )

    if sync_result["failed"] > 0:
        print(
            "存在向量同步失败任务，"
            "数据库记录已经保留，"
            "可以稍后重新执行同步。"
        )

    print(
        "\n导入流程完成。"
    )


if __name__ == "__main__":
    main()